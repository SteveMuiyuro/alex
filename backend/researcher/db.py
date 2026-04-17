from sqlalchemy import create_engine
from urllib.parse import quote_plus

DB_USER = "postgres"
DB_PASSWORD = quote_plus("2OXDK@/h-h},N/>h")  # ✅ FIX
DB_HOST = "34.42.135.13"
DB_NAME = "alex"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

engine = create_engine(DATABASE_URL)