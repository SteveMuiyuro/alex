import os
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel

# ✅ Service account
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/steve/Projects/alex/backend/alex-vertex-sa.json"

# ✅ Init
aiplatform.init(
    project="alex-prod-project",
    location="us-central1"
)

# ✅ NEW model (important fix)
model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# ✅ Generate embeddings
embeddings = model.get_embeddings(["vectorize me"])

print(len(embeddings[0].values))
print(embeddings[0].values[:5])