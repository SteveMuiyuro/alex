from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
import json
import os

# Auth
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "alex-vertex-sa.json"

# Init
aiplatform.init(
    project="alex-prod-project",
    location="us-central1"
)

# ✅ UPDATED MODEL
model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# Sample real data
documents = [
    {"id": "1", "text": "Apple stock is performing well in 2025"},
    {"id": "2", "text": "Tesla shares dropped due to market volatility"},
    {"id": "3", "text": "Microsoft shows strong cloud growth"}
]

output = []

for doc in documents:
    embedding = model.get_embeddings([doc["text"]])[0].values

    output.append({
        "id": doc["id"],
        "embedding": embedding,
        "restricts": []
    })

# Save JSONL (with .json extension)
with open("real_embeddings.json", "w") as f:
    for item in output:
        f.write(json.dumps(item) + "\n")

print("Saved real embeddings")