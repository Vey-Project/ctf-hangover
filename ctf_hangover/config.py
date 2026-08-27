"""Global configuration loaded from env / .env."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 9Router
    ninerouter_base_url: str = Field(default="http://192.168.0.78:20128/v1")
    ninerouter_api_key: str = Field(default="sk-none")
    ninerouter_models: str = Field(default="")
    coordinator_model: str = Field(default="gpt-5.4")

    # CTFd
    ctfd_url: str = Field(default="")
    ctfd_token: str = Field(default="")

    # Overkill knobs
    max_parallel_swarms: int = 8
    max_models_per_swarm: int = 4
    swarm_stuck_minutes: int = 5
    swarm_max_minutes: int = 30
    swarm_max_tokens: int = 500_000
    enable_selfplay: bool = True
    enable_auto_decompose: bool = True
    enable_smart_routing: bool = True

    # Sandbox
    sandbox_image: str = "ctf-hangover-sandbox:latest"
    workdir: str = "/tmp/ctf-hangover"

    @property
    def model_list(self) -> list[str]:
        return [m.strip() for m in self.ninerouter_models.split(",") if m.strip()]


settings = Settings()
