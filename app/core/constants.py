import os
from app.core.config import app_config
from dotenv import load_dotenv
load_dotenv()

MODEL_NAME = app_config["llm_settings"]["model_name"]
ENABLE_THINKING = app_config["llm_settings"]["enable_thinking"]
MAX_TOKENS = app_config["llm_settings"]["max_tokens"]
TEMPERATURE = app_config["llm_settings"]["temperature"]
REQUEST_TIMEOUT = app_config["system"]["request_timeout"]
MAX_RETRIES = app_config["system"]["max_retries"]
AMAP_API_KEY = os.getenv("AMAP_API_KEY")