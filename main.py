# uvicorn main:app --reload
from fastapi import FastAPI, HTTPException
import pickle
import numpy as np
from pydantic import BaseModel
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()

df = pd.read_csv("african_touristic_sites.csv") # updatable when model retrained
feature_matrix = pd.read_csv("dataSet.csv") # updatable when model retrained

@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello"}


# Define request body model
class UserPreferences(BaseModel):
    preferences: dict  # {feature_index: value}
    top_n: int = 5  # Default: return top 5 matches

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
        sites = df["Site_Name"].tolist()  # Extract site names
        recommendations = find_best_matches(data.preferences, feature_matrix, sites, data.top_n)
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))