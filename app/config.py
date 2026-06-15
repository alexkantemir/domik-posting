from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    DATABASE_URL: str = "sqlite:///./domik.db"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHANNEL_ID: str = ""
    TELEGRAM_GROUP_ID: str = ""

    # VK
    VK_COMMUNITY_TOKEN: str = ""
    VK_GROUP_ID: str = ""

    # GigaChat
    GIGACHAT_CLIENT_ID: str = ""
    GIGACHAT_CLIENT_SECRET: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"

    # Одноклассники
    OK_APP_ID: str = ""
    OK_PUBLIC_KEY: str = ""
    OK_SECRET_KEY: str = ""
    OK_GROUP_ID: str = ""

    # Яндекс Бизнес
    YANDEX_BUSINESS_API_KEY: str = ""
    YANDEX_ORG_ID: str = ""

    # Instagram / Meta
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_PAGE_ACCESS_TOKEN: str = ""
    INSTAGRAM_ACCOUNT_ID: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
