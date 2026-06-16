from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "智慧档案馆管理系统"
    DEBUG: bool = True
    
    DATABASE_URL: str = "sqlite:///./archive_management.db"
    
    SECRET_KEY: str = "your-secret-key-change-in-production-please-change-this-key-123456"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    TEMPERATURE_MAX: float = 24.0
    TEMPERATURE_MIN: float = 14.0
    HUMIDITY_MAX: float = 60.0
    HUMIDITY_MIN: float = 40.0
    
    OVERDUE_FINE_RATE_1: float = 5.0
    OVERDUE_FINE_RATE_2: float = 10.0
    OVERDUE_FINE_RATE_3: float = 20.0
    
    NOT_UTILIZED_YEARS: int = 30
    
    class Config:
        env_file = ".env"


settings = Settings()
