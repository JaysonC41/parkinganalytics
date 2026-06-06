import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_URL = os.getenv("DB_URL")

if not DB_URL:
    raise ValueError("DB_URL is missing. Add it to your .env file.")

engine = create_engine(DB_URL, pool_pre_ping=True)
