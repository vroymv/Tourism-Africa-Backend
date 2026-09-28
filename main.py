# uvicorn main:app --reload
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import json
import re
from fastapi.responses import JSONResponse

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Load datasets
DATA_DIR = Path(__file__).resolve().parent
df = pd.read_csv(DATA_DIR / "african_touristic_sites.csv")  # Updatable when model retrained
feature_matrix = pd.read_csv(DATA_DIR / "dataSet.csv")  # Updatable when model retrained

# Define feature columns mapping
feature_columns = {
    "Entry_Cost(USD)": 0,
    "Country_Safety_Index": 1,
    "Rating": 2,
    "Mobile_Network_Coverage": 3,
    "Geolocation_Type_desert": 4,
    "Geolocation_Type_island": 5,
    "Geolocation_Type_remote": 6,
    "Geolocation_Type_rural": 7,
    "Geolocation_Type_suburban": 8,
    "Geolocation_Type_urban": 9,
    "Category/Type_adventure": 10,
    "Category/Type_arid_region": 11,
    "Category/Type_historical_or_cultural": 12,
    "Category/Type_natural": 13,
    "Category/Type_religious": 14,
    "Category/Type_wildlife": 15,
    "Best_Time_to_Visit_any_time": 54,
    "Best_Time_to_Visit_dry_season": 55,
    "Best_Time_to_Visit_rainy_season": 56,
    "Available_Amenities_accessibilty_features": 57,
    "Available_Amenities_accommodation": 58,
    "Available_Amenities_cafeteria": 59,
    "Available_Amenities_guided_tours": 60,
    "Available_Amenities_hotels": 61,
    "Available_Amenities_none": 62,
    "Available_Amenities_parking": 63,
    "Available_Amenities_resort": 64,
    "Available_Amenities_restaurants": 65,
    "Available_Amenities_restrooms": 66,
    "Accessibility_air": 67,
    "Accessibility_boat": 68,
    "Accessibility_camel": 69,
    "Accessibility_foot": 70,
    "Accessibility_rail": 71,
    "Accessibility_vehicle": 72,
    "region_north": 73,
    "region_west": 74,
    "region_east": 75,
    "region_central": 76,
    "region_southern": 77
}

# Define scaling for numerical values
scaler_dict = {
    "Entry_Cost(USD)": MinMaxScaler().fit(np.array([[0], [1900]])),
    "Rating": MinMaxScaler().fit(np.array([[1], [5]])),
    "Country_Safety_Index": MinMaxScaler().fit(np.array([[1], [5]]))
}

# Define regions
country_regions = {
    "north": ['Algeria', 'Egypt', 'Libya', 'Morocco', 'Tunisia', 'Sudan'],
    "west": ['Benin', 'Burkina Faso', 'Cape Verde', 'Gambia', 'Ghana',
             'Guinea', 'Guinea-Bissau', 'Ivory Coast', 'Liberia', 'Mali',
             'Mauritania', 'Niger', 'Nigeria', 'Senegal', 'Sierra Leone', 'Togo'],
    "east": ['Burundi', 'Comoros', 'Djibouti', 'Eritrea', 'Ethiopia',
             'Kenya', 'Madagascar', 'Malawi', 'Mauritius', 'Mozambique',
             'Rwanda', 'Seychelles', 'Somalia', 'South Sudan', 'Tanzania', 'Uganda'],
    "central": ['Cameroon', 'Central African Republic', 'Chad', 'Congo',
                'Democratic Republic of the Congo', 'Equatorial Guinea', 'Gabon', 'São Tomé and Príncipe'],
    "southern": ['Angola', 'Botswana', 'Eswatini', 'Lesotho', 'Namibia',
                 'South Africa', 'Zambia', 'Zimbabwe']
}

COUNTRY_ALIASES = {
    "dr_congo": "drc",
    "democratic_republic_of_the_congo": "drc",
    "car": "central_african_republic",
    "republic_of_the_congo": "congo",
}


def normalize_country(value: str) -> str:
    country = re.sub(r"[\s-]+", "_", value.strip().lower())
    return COUNTRY_ALIASES.get(country, country)


def display_label(value: str) -> str:
    label = re.sub(r"_+", " ", value.strip()).title()
    return "DR Congo" if label.casefold() == "drc" else label


def parse_number(value):
    if value is None or pd.isna(value):
        return None
    cleaned = str(value).replace(",", "").replace("$", "").replace(" ", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _column_value(row, *column_names):
    columns = {str(column).casefold(): column for column in row.index}
    for name in column_names:
        column = columns.get(name.casefold())
        if column is not None:
            value = row[column]
            if value is not None and not pd.isna(value) and str(value).strip():
                return value
    return None


def _model_number(value, field: str):
    number = parse_number(value)
    if number is None:
        return None
    # The checked-in CSV stores these three model inputs after MinMax scaling.
    if 0 <= number <= 1:
        if field == "Entry_Cost(USD)":
            return number * 1900
        if field in {"Rating", "Country_Safety_Index"}:
            return 1 + number * 4
    return number


def _split_values(value):
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            decoded = json.loads(text)
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        except (TypeError, ValueError):
            pass
    return [item.strip() for item in re.split(r"[,;|]", text) if item.strip()]


def _deduplicated_labels(values):
    labels = []
    seen = set()
    for value in values:
        label = display_label(str(value).replace(" ", "_").lower())
        if label and label.casefold() not in seen:
            seen.add(label.casefold())
            labels.append(label)
    return labels


def _truthy_feature(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    number = parse_number(value)
    return number is not None and number > 0


def _labels_for_site(row, fields, feature_prefixes=()):
    values = []
    for field in fields:
        values.extend(_split_values(_column_value(row, field)))
    for column in row.index:
        for prefix in feature_prefixes:
            if str(column).casefold().startswith(prefix.casefold()):
                if _truthy_feature(row[column]):
                    values.append(str(column)[len(prefix):])
                break
    return _deduplicated_labels(values)


def _country_key(value) -> str:
    return normalize_country(str(value))


def _site_image(row):
    image_values = []
    for field in ("site_images", "Site_Images", "image", "Image"):
        image_values.extend(_split_values(_column_value(row, field)))
    return next((image for image in image_values if image.startswith("https://")), None)


@app.middleware("http")
async def cache_country_responses(request, call_next):
    response = await call_next(request)
    if request.url.path == "/countries" or request.url.path.startswith("/countries/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.get("/countries")
def list_countries() -> dict:
    countries = df["Country"].fillna("").map(lambda value: str(value).strip().lower())
    counts = countries[countries != ""].value_counts()
    results = []
    for country, count in counts.items():
        country = str(country)
        results.append({
            "slug": re.sub(r"[\s-]+", "_", country),
            "name": display_label(country),
            "siteCount": int(count),
        })
    results.sort(key=lambda country: (-country["siteCount"], country["name"].casefold()))
    return {"countries": results}


@app.get("/countries/{country:path}", response_model=None)
def get_country(country: str) -> dict | JSONResponse:
    normalized_country = normalize_country(country)
    if not re.fullmatch(r"[a-z_]{2,64}", normalized_country):
        raise HTTPException(status_code=400, detail="Invalid country")

    country_rows = df[df["Country"].map(_country_key) == normalized_country]
    if country_rows.empty:
        return JSONResponse(status_code=404, content={"error": "Country not found"})

    sites = []
    ratings = []
    safety_indices = []
    visitor_counts = []
    entry_costs = []
    for _, row in country_rows.iterrows():
        rating = _model_number(_column_value(row, "Rating", "rating"), "Rating")
        safety = _model_number(
            _column_value(row, "Country_Safety_Index", "country_safety_index"),
            "Country_Safety_Index",
        )
        visitors = parse_number(_column_value(row, "annualVisitors", "annual_visitors", "Total_Annual_Visitors"))
        entry_cost = _model_number(
            _column_value(row, "Entry_Cost(USD)", "entryCostUsd", "entry_cost_usd"),
            "Entry_Cost(USD)",
        )
        if rating is not None:
            ratings.append(rating)
        if safety is not None:
            safety_indices.append(safety)
        if visitors is not None:
            visitor_counts.append(visitors)
        if entry_cost is not None:
            entry_costs.append(entry_cost)

        sites.append({
            "id": _column_value(row, "Site_ID", "id"),
            "name": display_label(str(_column_value(row, "Site_Name", "name") or "")),
            "city": _column_value(row, "City", "city"),
            "categories": _labels_for_site(row, ("categories", "category"), ("Category/Type_",)),
            "primaryAttractions": _labels_for_site(row, ("primaryAttractions", "primary_attractions"), ("Primary_Attraction_",)),
            "description": _column_value(row, "Description", "description"),
            "rating": rating,
            "annualVisitors": visitors,
            "entryCostUsd": entry_cost,
            "image": _site_image(row),
        })

    sites.sort(key=lambda site: (site["rating"] is None, -(site["rating"] or 0), str(site["id"] or "")))
    country_name = display_label(normalized_country)
    currencies = list(dict.fromkeys(
        value.upper()
        for _, row in country_rows.iterrows()
        for value in _split_values(_column_value(row, "currency", "currencies", "Currency"))
    ))
    airports = _deduplicated_labels(
        [value for _, row in country_rows.iterrows() for value in _split_values(_column_value(row, "airports", "Airports"))]
    )

    return {"country": {
        "slug": normalized_country,
        "name": country_name,
        "siteCount": int(len(country_rows)),
        "averageRating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "safetyIndex": round(sum(safety_indices) / len(safety_indices), 1) if safety_indices else None,
        "totalAnnualVisitors": sum(visitor_counts) if visitor_counts else None,
        "entryCostUsd": {
            "min": min(entry_costs) if entry_costs else None,
            "max": max(entry_costs) if entry_costs else None,
        },
        "currencies": currencies,
        "bestTimesToVisit": _labels_for_country(country_rows, ("bestTimesToVisit", "best_times_to_visit"), ("Best_Time_to_Visit_",)),
        "categories": _labels_for_country(country_rows, ("categories", "category"), ("Category/Type_",)),
        "airports": airports,
        "sites": sites,
    }}


def _labels_for_country(rows, fields, feature_prefixes=()):
    values = []
    for _, row in rows.iterrows():
        values.extend(_labels_for_site(row, fields, feature_prefixes))
    return _deduplicated_labels(values)


@app.get("/about")
def about() -> dict[str, str]:
    return {"message": "This is the about page."}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello"}


# Define request body model
class UserPreferences(BaseModel):
    preferences: dict = Field(max_length=80)  # {feature_name: value}
    top_n: int = Field(default=5, ge=1, le=20)


# with user input as text
def preprocess_user_input(user_input, feature_columns, scaler_dict, country_regions):

    """
    Convert user input dictionary into a numerical format matching the feature matrix.

    Args:
        user_input (dict): Raw user preferences from the web app.
        feature_columns (dict): Mapping of feature names to their column indices.
        scaler_dict (dict): Pre-fitted MinMaxScaler objects for numerical features.
        mlb_dict (dict): MultiLabelBinarizer mappings for multi-hot encoded features.
        country_regions (dict): Mapping of countries to regional binary features.

    Returns:
        dict: Processed user preferences with numerical indices as keys.
    """

    # Initialize processed input with all features set to 0
    processed_input = {index: 0 for index in feature_columns.values()}

    # Handle numerical features (normalize)
    numerical_features = ["Entry_Cost(USD)", "Country_Safety_Index", "Rating"]
    for feature in numerical_features:
        if feature in feature_columns:
            feature_key = feature.replace("(USD)", "").lower().replace(" ", "_")
            if feature_key in user_input:
                value = float(user_input[feature_key])
                # Normalize using corresponding MinMaxScaler
                processed_input[feature_columns[feature]] = scaler_dict[feature].transform([[value]])[0, 0]

    # Handle Mobile Network Coverage (Yes - 2, Limited - 1, No - 0)
    if "mobileNetworkCoverage" in user_input and "Mobile_Network_Coverage" in feature_columns:
        coverage_mapping = {"yes": 2, "limited": 1, "no": 0}
        processed_input[feature_columns["Mobile_Network_Coverage"]] = coverage_mapping.get(user_input["mobileNetworkCoverage"].lower(), 0)


    # Handle categorical one-hot encoding (e.g., Geolocation Type, Category)
    categorical_features = [
        ("geolocationtype", "Geolocation_Type_"),
        ("category", "Category/Type_"),
        ("bestTimeToVisit", "Best_Time_to_Visit_"),
    ]
    for user_key, prefix in categorical_features:
        if user_key in user_input:
            categories = user_input[user_key] if isinstance(user_input[user_key], list) else [user_input[user_key]]
            for category in categories:
                feature_name = f"{prefix}{category}"
                if feature_name in feature_columns:
                    processed_input[feature_columns[feature_name]] = 1

    # Handle Primary Attractions
    if "primaryAttractions" in user_input:
        for attraction in user_input["primaryAttractions"]:
            feature_name = f"Primary_Attraction_{attraction}"
            if feature_name in feature_columns:
                processed_input[feature_columns[feature_name]] = 1

    # Handle Available Amenities
    if "amenities" in user_input:
        for amenity in user_input["amenities"]:
            feature_name = f"Available_Amenities_{amenity}"
            if feature_name in feature_columns:
                processed_input[feature_columns[feature_name]] = 1

    # Handle Accessibility
    if "accessibility" in user_input:
        access_key = f"Accessibility_{user_input['accessibility']}"
        if access_key in feature_columns:
            processed_input[feature_columns[access_key]] = 1

    # Handle Country and Region
    if "country" in user_input:
        country = user_input["country"]
        for region, countries in country_regions.items():
            if country in countries:
                region_key = f"region_{region}"
                if region_key in feature_columns:
                    processed_input[feature_columns[region_key]] = 1
                break  # Ensure only one region is selected

    return processed_input


# without weights considered
def find_best_matches(user_preferences, feature_matrix, sites, top_n=5):
    """
    Find the top N best site matches based on user preferences, even if some values are missing.

    Args:
        user_preferences (dict): Dictionary of feature indices and values provided by the user.
        feature_matrix (pd.DataFrame): The preprocessed dataset matrix.
        sites (list): List of site names.
        top_n (int): Number of matches to return (default=5).

    Returns:
        list: List of recommended site names.
    """
    # Extract the indices of provided features
    provided_indices = list(user_preferences.keys())

    if not provided_indices:
        return ["No preferences provided. Cannot make a recommendation."]

    # Convert feature matrix to only the provided features
    reduced_feature_matrix = feature_matrix.iloc[:, provided_indices]

    # Convert user preferences into a vector matching the reduced feature matrix
    user_vector = np.array([user_preferences[i] for i in provided_indices]).reshape(1, -1)

    # Compute similarity between user preferences and available features of sites
    similarities = cosine_similarity(user_vector, reduced_feature_matrix)[0]

    # Get indices of the top N most similar sites
    top_n_indices = np.argsort(similarities)[-top_n:][::-1]  # Sort in descending order

    return [sites[i] for i in top_n_indices]


@app.post("/recommend", include_in_schema=False)
@app.post("/recommend/")
def recommend_sites(data: UserPreferences):
    try:
        # Preprocess user preferences before passing to the recommendation function
        processed_preferences = preprocess_user_input(data.preferences, feature_columns, scaler_dict, country_regions)

        sites = df["Site_Name"].tolist()  # Extract site names
        recommendations = find_best_matches(processed_preferences, feature_matrix, sites, data.top_n)

        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# AWS Lambda Function URLs send API Gateway v2 events to this adapter.
handler = Mangum(app)
