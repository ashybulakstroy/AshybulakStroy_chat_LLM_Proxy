from app.providers.openai_provider import OpenAIProvider


CLOUDFLARE_WORKERS_AI_CHAT_MODELS = [
    "@cf/meta/llama-3.1-8b-instruct",
]


class CloudflareWorkersAIProvider(OpenAIProvider):
    async def get_models(self) -> dict:
        return {
            "object": "list",
            "data": [
                {
                    "id": model_id,
                    "object": "model",
                    "provider": self.provider_name,
                    "supports_chat": True,
                    "category": "llm",
                }
                for model_id in CLOUDFLARE_WORKERS_AI_CHAT_MODELS
            ],
        }
