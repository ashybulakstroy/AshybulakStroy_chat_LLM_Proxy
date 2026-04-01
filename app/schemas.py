from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str = Field(..., examples=["Ассаламу Алейкум!"])
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., examples=["llama-3.1-8b-instant"])
    messages: List[Message]
    temperature: Optional[float] = Field(default=1.0, examples=[1.0])
    top_p: Optional[float] = Field(default=1.0, examples=[1.0])
    max_tokens: Optional[int] = Field(default=None, examples=[32])
    provider: Optional[str] = Field(
        default=None,
        description="Имя провайдера. Используйте 'auto' для выбора по блоку рекомендаций.",
        examples=["auto", "groq"],
    )
    metadata: Optional[dict[str, Any]] = None


class EmbeddingRequest(BaseModel):
    model: str = Field(..., examples=["text-embedding-3-small"])
    input: Union[str, List[str]]
    provider: Optional[str] = Field(
        default=None,
        description="Имя провайдера или 'auto', если появится поддержка авто-выбора для embeddings.",
        examples=["groq"],
    )
    metadata: Optional[dict[str, Any]] = None


class ModelInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None


class ProxyResponse(BaseModel):
    data: Any
