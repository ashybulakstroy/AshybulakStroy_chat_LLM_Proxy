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

    EDENAI_API_KEY: str = os.getenv("EDENAI_API_KEY", "")
    EDENAI_API_BASE: str = os.getenv("EDENAI_API_BASE", "https://api.edenai.run/v3/llm")

    FIREWORKS_API_KEY: str = os.getenv("FIREWORKS_API_KEY", "")
    FIREWORKS_API_BASE: str = os.getenv("FIREWORKS_API_BASE", "https://api.fireworks.ai/inference/v1")

    ENABLE_PROVIDER_LOG: bool = os.getenv("ENABLE_PROVIDER_LOG", "false").lower() in ("1", "true", "yes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    PROXY_MODE: str = os.getenv("PROXY_MODE", "LOAD_BALANCE").upper()
    ALLOW_RUNTIME_ADMIN_MUTATIONS: bool = os.getenv("ALLOW_RUNTIME_ADMIN_MUTATIONS", "false").lower() in ("1", "true", "yes")

    P2P_ENABLED: bool = os.getenv("P2P_ENABLED", "false").lower() in ("1", "true", "yes")
    NODE_MODE: str = os.getenv("NODE_MODE", "peer").strip().lower()
    P2P_SCOPE: str = os.getenv("P2P_SCOPE", "private").strip().lower()
    P2P_NODE_NAME: str = os.getenv("P2P_NODE_NAME", "home-node").strip() or "home-node"
    P2P_NODE_ID: str = os.getenv("P2P_NODE_ID", "").strip()
    P2P_CLUSTER_NAME: str = os.getenv("P2P_CLUSTER_NAME", "default").strip() or "default"
    P2P_BASE_URL: str = os.getenv("P2P_BASE_URL", "").strip()
    P2P_MASTER_URL: str = os.getenv("P2P_MASTER_URL", "").strip()
    P2P_ALLOW_MASTER: bool = os.getenv("P2P_ALLOW_MASTER", "true").lower() in ("1", "true", "yes")
    P2P_ACCEPT_REMOTE_TASKS: bool = os.getenv("P2P_ACCEPT_REMOTE_TASKS", "true").lower() in ("1", "true", "yes")
    P2P_SHARE_CAPACITY: bool = os.getenv("P2P_SHARE_CAPACITY", "true").lower() in ("1", "true", "yes")
    P2P_SHARED_RPM_RATIO: float = float(os.getenv("P2P_SHARED_RPM_RATIO", "1.0"))
    P2P_SHARED_TPM_RATIO: float = float(os.getenv("P2P_SHARED_TPM_RATIO", "1.0"))
    P2P_MAX_CLIENT_SLOTS_PER_MIN: int = int(os.getenv("P2P_MAX_CLIENT_SLOTS_PER_MIN", "1"))
    P2P_MAX_SHARED_SLOTS_PER_MIN: int = int(os.getenv("P2P_MAX_SHARED_SLOTS_PER_MIN", "5"))
    P2P_MAX_REMOTE_SESSIONS: int = int(os.getenv("P2P_MAX_REMOTE_SESSIONS", "3"))
    P2P_MAX_OUTGOING_SESSIONS: int = int(os.getenv("P2P_MAX_OUTGOING_SESSIONS", "5"))
    P2P_MAX_QUEUE_SIZE: int = int(os.getenv("P2P_MAX_QUEUE_SIZE", "50"))
    P2P_SESSION_TIMEOUT_SEC: int = int(os.getenv("P2P_SESSION_TIMEOUT_SEC", "90"))
    P2P_PER_PEER_RPM_LIMIT: int = int(os.getenv("P2P_PER_PEER_RPM_LIMIT", "20"))
    P2P_PER_TARGET_PEER_RPM_LIMIT: int = int(os.getenv("P2P_PER_TARGET_PEER_RPM_LIMIT", "20"))
    P2P_GLOBAL_INCOMING_RPM_LIMIT: int = int(os.getenv("P2P_GLOBAL_INCOMING_RPM_LIMIT", "60"))
    P2P_GLOBAL_OUTGOING_RPM_LIMIT: int = int(os.getenv("P2P_GLOBAL_OUTGOING_RPM_LIMIT", "60"))
    P2P_HEARTBEAT_INTERVAL_SEC: int = int(os.getenv("P2P_HEARTBEAT_INTERVAL_SEC", "15"))
    P2P_PEER_STALE_AFTER_SEC: int = int(os.getenv("P2P_PEER_STALE_AFTER_SEC", "45"))
    P2P_ROUTE_TTL_MIN: int = int(os.getenv("P2P_ROUTE_TTL_MIN", "1440"))

    def get_provider_configs(self) -> Dict[str, ProviderConfig]:
        configs = {
            "openai": ProviderConfig("openai", self.OPENAI_API_KEY, self.OPENAI_API_BASE),
            "groq": ProviderConfig("groq", self.GROQ_API_KEY, self.GROQ_API_BASE),
            "openrouter": ProviderConfig("openrouter", self.OPENROUTER_API_KEY, self.OPENROUTER_API_BASE),
            "cerebras": ProviderConfig("cerebras", self.CEREBRAS_API_KEY, self.CEREBRAS_API_BASE),
            "gemini": ProviderConfig("gemini", self.GEMINI_API_KEY, self.GEMINI_API_BASE),
            "sambanova": ProviderConfig("sambanova", self.SAMBANOVA_API_KEY, self.SAMBANOVA_API_BASE),
            "edenai": ProviderConfig("edenai", self.EDENAI_API_KEY, self.EDENAI_API_BASE),
            "fireworks": ProviderConfig("fireworks", self.FIREWORKS_API_KEY, self.FIREWORKS_API_BASE),
        }
        return {name: config for name, config in configs.items() if config.api_key}


settings = Settings()
