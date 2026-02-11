from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"  # easiest for now (no Postgres yet)

    STRIPE_SECRET_KEY: str = "sk_test_replace_me"
    STRIPE_WEBHOOK_SECRET: str = "whsec_replace_me"

    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_SUCCESS_URL: str = "http://localhost:8000/success"
    FRONTEND_CANCEL_URL: str = "http://localhost:8000/cancel"

    TELEGRAM_BOT_TOKEN: str = "replace_me"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
