import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Currency Exchange Rates Service")


@app.get("/health")
def health():
    logging.info("Health check called")
    return {"status": "ok"}


@app.get("/")
def run():
    logging.info("Root endpoint called")
    return {
        "message": "Currency Exchange Rates pipeline placeholder",
        "project_id": os.getenv("PROJECT_ID", "local-dev"),
    }