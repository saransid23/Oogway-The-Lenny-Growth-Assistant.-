import json
import logging
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
import httpx
from app.config import settings

logger = logging.getLogger("lenny_assistant.ollama")

class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_client(self) -> httpx.AsyncClient:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._client is None or self._client.is_closed or (self._client_loop is not None and self._client_loop != current_loop):
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=3.0))
            self._client_loop = current_loop
        elif self._client_loop is None and current_loop is not None:
            self._client_loop = current_loop

        return self._client

    async def aclose(self):
        """Closes the shared HTTP client session cleanly."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._client_loop = None

    async def check_health(self) -> bool:
        try:
            client = self._get_client()
            res = await client.get(f"{self.base_url}/api/tags", timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
        target_model = model or self.model
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "num_predict": settings.OLLAMA_NUM_PREDICT,
                "temperature": 0.2
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            client = self._get_client()
            res = await client.post(url, json=payload, timeout=httpx.Timeout(90.0, connect=3.0))
            if res.status_code == 200:
                data = res.json()
                return data.get("response", "")
            return None
        except Exception as e:
            logger.warning(f"Ollama generation exception: {e}")
            return None

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        target_model = model or self.model
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "num_predict": settings.OLLAMA_NUM_PREDICT,
                "temperature": 0.2
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        client = self._get_client()
        try:
            async with client.stream("POST", url, json=payload, timeout=httpx.Timeout(90.0, connect=3.0)) as response:
                if response.status_code != 200:
                    logger.warning(f"Ollama stream returned status {response.status_code}")
                    return
                async for line in response.aiter_lines():
                    if not line or not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
        except Exception as e:
            logger.warning(f"Ollama stream_generate exception: {e}")
            return

    async def embed(self, text: str) -> Optional[List[float]]:
        try:
            client = self._get_client()
            url = f"{self.base_url}/api/embeddings"
            payload = {
                "model": settings.OLLAMA_EMBED_MODEL,
                "prompt": text,
                "keep_alive": settings.OLLAMA_KEEP_ALIVE
            }
            res = await client.post(url, json=payload, timeout=settings.EMBED_TIMEOUT_SECONDS)
            if res.status_code == 200:
                data = res.json()
                return data.get("embedding")
            return None
        except Exception as e:
            logger.debug(f"Ollama embed call failed: {e}")
            return None

ollama_client = OllamaClient()
