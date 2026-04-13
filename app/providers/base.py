from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ProviderBase(ABC):
    @abstractmethod
    async def get_models(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_chat_completion(self, request: Any) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_embeddings(self, request: Any) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_audio_transcription(self, request: Any) -> Dict[str, Any]:
        raise NotImplementedError
