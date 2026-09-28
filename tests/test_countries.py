import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def country_data(monkeypatch):
    monkeypatch.setattr(
        main,
        "df",
        pd.DataFrame(
            [
                {
                    "Site_ID": "S0045",
                    "Site_Name": "table_mountain",
                    "Country": " south_africa ",
                    "City": "Cape Town",
                    "Description": "A famous mountain.",
                    "Rating": 0.75,
                    "Country_Safety_Index": 0.25,
                    "Entry_Cost(USD)": 0.1,
                    "annual_visitors": "1,000,000",
                    "Currency": "zar",
                    "Best_Time_to_Visit_dry_season": 1,
                    "Category/Type_wildlife": 1,
                    "Primary_Attraction_mountain": 1,
                    "site_images": "not-an-image,https://example.com/table.jpg",
                    "Airports": "Cape Town International",
                },
                {
                    "Site_ID": "S0046",
                    "Site_Name": "kruger_national_park",
                    "Country": "south_africa",
                    "Rating": 0.5,
                    "Country_Safety_Index": 0.5,
                    "Entry_Cost(USD)": 0.2,
                    "annual_visitors": "10,00,000",
                    "Currency": "ZAR",
                    "Best_Time_to_Visit_dry_season": 1,
                    "Category/Type_wildlife": 1,
                    "Category/Type_adventure": 1,
                    "Primary_Attraction_mountain": 0,
                    "site_images": "http://example.com/not-secure.jpg",
                },
                {
                    "Site_ID": "S0100",
                    "Site_Name": "gorilla_sanctuary",
                    "Country": "drc",
                    "Rating": 1.0,
                    "Country_Safety_Index": 0.5,
                    "Entry_Cost(USD)": 0.1,
                },
            ]
        ),
    )
    with TestClient(main.app) as client:
        yield client


def test_list_countries_counts_and_sorts(country_data):
    response = country_data.get("/countries")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json() == {
        "countries": [
            {"slug": "south_africa", "name": "South Africa", "siteCount": 2},
            {"slug": "drc", "name": "DR Congo", "siteCount": 1},
        ]
    }


def test_country_details_normalize_and_aggregate(country_data):
    response = country_data.get("/countries/South-Africa")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    payload = response.json()["country"]
    assert payload["slug"] == "south_africa"
    assert payload["name"] == "South Africa"
    assert payload["siteCount"] == 2
    assert payload["averageRating"] == 3.5
    assert payload["safetyIndex"] == 2.5
    assert payload["totalAnnualVisitors"] == 2_000_000
    assert payload["entryCostUsd"] == {"min": 190, "max": 380}
    assert payload["currencies"] == ["ZAR"]
    assert payload["bestTimesToVisit"] == ["Dry Season"]
    assert payload["categories"] == ["Wildlife", "Adventure"]
    assert payload["airports"] == ["Cape Town International"]
    assert [site["id"] for site in payload["sites"]] == ["S0045", "S0046"]
    assert payload["sites"][0]["name"] == "Table Mountain"
    assert payload["sites"][0]["primaryAttractions"] == ["Mountain"]
    assert payload["sites"][0]["image"] == "https://example.com/table.jpg"
    assert payload["sites"][1]["image"] is None
    assert payload["sites"][1]["city"] is None


def test_country_alias_and_input_validation(country_data):
    assert country_data.get("/countries/DR-Congo").json()["country"]["slug"] == "drc"
    invalid = country_data.get("/countries/not-valid!")
    assert invalid.status_code == 400
    assert invalid.headers["cache-control"] == "public, max-age=3600"


def test_unknown_country_has_expected_error_body(country_data):
    response = country_data.get("/countries/unknown_country")

    assert response.status_code == 404
    assert response.json() == {"error": "Country not found"}


def test_parse_number_supports_mixed_thousands_format():
    assert main.parse_number("10,00,000") == 1_000_000
    assert main.parse_number("$ 1,250") == 1250
    assert main.parse_number("1 250") == 1250
    assert main.parse_number("free") is None
    assert main.parse_number("") is None
