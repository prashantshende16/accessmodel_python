import os
from typing import List

class Settings:
    PROJECT_NAME: str = "ErrorWatch Monitoring Platform"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "errorwatch-production-secret-key-salt-9876543210")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'errorwatch.db')}"
    )
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ]

settings = Settings()
