from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
import os

# Auth
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "alex-vertex-sa.json"

# Init
aiplatform.init(
    project="alex-prod-project",
    location="us-central1"
)

# Real embedding model
model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# Query text
query = "Apple stock growth"

# Generate embedding (768 dim)
query_embedding = model.get_embeddings([query])[0].values

# Endpoint
endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name="projects/78286319237/locations/us-central1/indexEndpoints/3875886240049922048"
)

# Query index
response = endpoint.find_neighbors(
    deployed_index_id="alex_deployed_index_768",
    queries=[query_embedding],
    num_neighbors=2
)

print(response)