import logging
import httpx
from typing import Optional
from app.config import settings

try:
    import anthropic
    from anthropic import AsyncAnthropic
except ImportError:
    anthropic = None
    AsyncAnthropic = None

logger = logging.getLogger("lenny_assistant.cloud_client")

class CloudLLMClient:
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.anthropic_key = settings.ANTHROPIC_API_KEY
        self.anthropic_client: Optional[AsyncAnthropic] = None
        if self.anthropic_key and AsyncAnthropic:
            try:
                self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_key)
            except Exception as e:
                logger.warning(f"Could not initialize AsyncAnthropic: {e}")

    async def check_health(self) -> bool:
        return bool(self.openai_key or self.anthropic_key)

    async def generate_openai(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        if not self.openai_key:
            return None
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.3
        }

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                return None
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return None

    async def generate_anthropic(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        if not self.anthropic_key:
            return None

        # 1. Primary: Official Anthropic Python SDK
        if self.anthropic_client:
            try:
                kwargs = {
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if system_prompt:
                    kwargs["system"] = system_prompt

                response = await self.anthropic_client.messages.create(**kwargs)
                if response and response.content:
                    text_parts = [block.text for block in response.content if hasattr(block, "text")]
                    return "".join(text_parts)
            except Exception as e:
                logger.error(f"Anthropic SDK error: {e}")

        # 2. Resilient fallback: Raw HTTP endpoint
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["content"][0]["text"]
                return None
        except Exception as e:
            logger.error(f"Anthropic HTTP fallback error: {e}")
            return None

cloud_client = CloudLLMClient()

