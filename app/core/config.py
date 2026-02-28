import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM Settings
    LLM_SERVICE_BASE_URL: str = "https://example.com/v1"
    API_KEY: str = "your_api_key_here"
    LLM_MODEL: str = "Claude Sonnet 3.5"
    
    # Notification Settings
    FEISHU_WEBHOOK_URL: str = "https://open.feishu.cn/open-apis/bot/v2/hook/..."
    
    # Arxiv Settings
    ARXIV_QUERY: str = "cat:cs.AI"
    ARXIV_MAX_RESULTS: int = 200
    
    # Aliyun OSS Settings
    ALIYUN_OSS_ACCESS_KEY_ID: str = ""
    ALIYUN_OSS_ACCESS_KEY_SECRET: str = ""
    ALIYUN_OSS_ENDPOINT: str = ""
    ALIYUN_OSS_BUCKET: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
