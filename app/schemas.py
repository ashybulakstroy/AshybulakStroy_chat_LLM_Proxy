from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(..., examples=["user"])
    content: Any = Field(..., examples=["Ассаламу алейкум!"])
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., examples=["llama-3.1-8b-instant"])
    messages: List[Message]
    temperature: Optional[float] = Field(default=1.0, examples=[1.0])
    top_p: Optional[float] = Field(default=1.0, examples=[1.0])
    max_tokens: Optional[int] = Field(default=None, examples=[32])
    provider: Optional[str] = Field(
        default=None,
        description="Имя провайдера. Используйте 'auto' для автоматического выбора по логике proxy.",
        examples=["auto", "groq"],
    )
    resource_affinity: Optional[str] = Field(
        default="auto",
        description="Политика привязки клиента к одному и тому же внутреннему ресурсу. 'sticky' старается держать клиента на прежнем provider+model, если ресурс доступен.",
        examples=["auto", "sticky"],
    )
    response_type: Optional[str] = Field(
        default="json",
        description="Ожидаемый тип ответа: json, text, audio, video.",
        examples=["json", "text", "audio", "video"],
    )
    metadata: Optional[dict[str, Any]] = None


class EmbeddingRequest(BaseModel):
    model: str = Field(..., examples=["text-embedding-3-small"])
    input: Union[str, List[str]]
    provider: Optional[str] = Field(
        default=None,
        description="Имя провайдера или 'auto', если позже будет включена авто-маршрутизация для embeddings.",
        examples=["groq", "auto"],
    )
    metadata: Optional[dict[str, Any]] = None


class ModelInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None


class ProxyResponse(BaseModel):
    data: Any
