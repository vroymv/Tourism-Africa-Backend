# uvicorn main:app --reload
from fastapi import FastAPI, HTTPException
import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

app = FastAPI()

# Load datasets
df = pd.read_csv("african_touristic_sites.csv")  # Updatable when model retrained
feature_matrix = pd.read_csv("dataSet.csv")  # Updatable when model retrained

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
    "Entry_Cost(USD)": MinMaxScaler().fit([[0], [1900]]),
    "Rating": MinMaxScaler().fit([[1], [5]]),
    "Country_Safety_Index": MinMaxScaler().fit([[1], [5]])
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


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello"}


# Define request body model
class UserPreferences(BaseModel):
    preferences: dict  # {feature_name: value}
    top_n: int = 5  # Default: return top 5 matches


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


def find_best_matches(user_preferences, feature_matrix, sites, top_n=5):
    provided_indices = list(map(int, user_preferences.keys()))  # Convert keys to integers

    if not provided_indices:
        return ["No preferences provided. Cannot make a recommendation."]

    reduced_feature_matrix = feature_matrix.iloc[:, provided_indices]
    user_vector = np.array([user_preferences[str(i)] for i in provided_indices]).reshape(1, -1)

    similarities = cosine_similarity(user_vector, reduced_feature_matrix)[0]
    top_n_indices = np.argsort(similarities)[-top_n:][::-1]

    return [sites[i] for i in top_n_indices]


@app.post("/recommend/")
def recommend_sites(data: UserPreferences):
    try:
        # Preprocess user preferences before passing to the recommendation function
        processed_preferences = preprocess_user_input(data.preferences)

        sites = df["Site_Name"].tolist()  # Extract site names
        recommendations = find_best_matches(processed_preferences, feature_matrix, sites, data.top_n)

        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
