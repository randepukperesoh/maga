from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "rod-system-designer-api"
    api_prefix: str = "/api/v1"


settings = Settings()
