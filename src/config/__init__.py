import logging
import os

from dotenv import load_dotenv

load_dotenv()

COMFY_ENDPOINTS = [url.strip() for url in os.getenv("COMFY_SERVERS", "localhost:8188").split(",")]

AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION_NAME = os.getenv("S3_REGION_NAME", "")

RDB_USERNAME = os.getenv("RDB_USERNAME", "root")
RDB_PASSWORD = os.getenv("RDB_PASSWORD", "123456")
RDB_HOST = os.getenv("RDB_HOST", "localhost")
RDB_PORT = os.getenv("RDB_PORT", 5432)
RDB_NAME = os.getenv("RDB_NAME", "comfy")

CALL_BACK_BASE_URL = os.getenv("CALL_BACK_BASE_URL", "")
FALLBACK_PATH = os.getenv("FALLBACK_PATH", "fallback")
SERVICE_PORT = os.getenv("SERVICE_PORT", 8000)
ROUTE_PREFIX = os.getenv("ROUTE_PREFIX", "/api/v1")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
