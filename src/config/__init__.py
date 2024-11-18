import logging
import os

from dotenv import load_dotenv

load_dotenv()

COMFY_HOST = os.getenv('COMFY_HOST', 'localhost')
COMFY_PORT = os.getenv('COMFY_PORT', 8188)
COMFY_CLIENT_ID = os.getenv('COMFY_CLIENT_ID', '7777777')  # client id for the comfy client

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
