from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    # Empty by default so local dev is unaffected -- the access gate middleware only enforces
    # the key when this is set to a non-empty value.
    access_key: str = ""
    # Comma-separated list of allowed frontend origins for CORS.
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Strip stray whitespace/newlines from copy-pasted values, and accept the plain
        # postgresql:// scheme Railway hands out -- psycopg2 needs the +psycopg2 driver segment.
        value = value.strip()
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg2://" + value[len("postgresql://") :]
        return value

    @field_validator("access_key", mode="after")
    @classmethod
    def _strip_access_key(cls, value: str) -> str:
        # Same copy-paste trailing whitespace/newline issue as DATABASE_URL -- strip it so a
        # correctly-typed key isn't rejected by a stray character baked into the Railway value.
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
