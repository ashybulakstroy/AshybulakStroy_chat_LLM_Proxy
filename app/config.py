import os
from dataclasses import dataclass
from typing import Dict

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    api_base: str


class Settings:
    PORT: int = int(os.getenv("PORT", "8800"))

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_BASE: str = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE: str = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

    CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
    CEREBRAS_API_BASE: str = os.getenv("CEREBRAS_API_BASE", "https://api.cerebras.ai/v1")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_API_BASE: str = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai/")

    SAMBANOVA_API_KEY: str = os.getenv("SAMBANOVA_API_KEY", "")
    SAMBANOVA_API_BASE: str = os.getenv("SAMBANOVA_API_BASE", "https://api.sambanova.ai/v1")

    ENABLE_PROVIDER_LOG: bool = os.getenv("ENABLE_PROVIDER_LOG", "false").lower() in ("1", "true", "yes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def get_provider_configs(self) -> Dict[str, ProviderConfig]:
        configs = {
            "openai": ProviderConfig("openai", self.OPENAI_API_KEY, self.OPENAI_API_BASE),
            "groq": ProviderConfig("groq", self.GROQ_API_KEY, self.GROQ_API_BASE),
            "openrouter": ProviderConfig("openrouter", self.OPENROUTER_API_KEY, self.OPENROUTER_API_BASE),
            "cerebras": ProviderConfig("cerebras", self.CEREBRAS_API_KEY, self.CEREBRAS_API_BASE),
            "gemini": ProviderConfig("gemini", self.GEMINI_API_KEY, self.GEMINI_API_BASE),
            "sambanova": ProviderConfig("sambanova", self.SAMBANOVA_API_KEY, self.SAMBANOVA_API_BASE),
        }
        return {name: config for name, config in configs.items() if config.api_key}


settings = Settings()
