from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent_graph.schemas import Hypothesis


class BaseJSONClient(ABC):
    def __init__(self, model: str, api_key: str, timeout_seconds: int = 30, max_retries: int = 3) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def available(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _post_json(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        backoff_seconds = 1.0
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            request = Request(url, data=payload, headers=headers, method="POST")
            try:
                with urlopen(request, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code} from LLM provider: {detail}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue
                raise RuntimeError(f"Network error from LLM provider: {exc}") from exc

        raise RuntimeError(f"LLM request failed after retries: {last_error}")


class OpenAIJSONClient(BaseJSONClient):
    def __init__(self, model: str | None = None) -> None:
        super().__init__(
            model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available():
            raise RuntimeError("OPENAI_API_KEY is not set")

        body = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(prompt),
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": name,
                    "schema": schema,
                }
            },
        }
        payload = self._post_json(
            "https://api.openai.com/v1/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            body=body,
        )
        text = payload.get("output_text")
        if not text:
            for item in payload.get("output", []) or []:
                for content in item.get("content", []) or []:
                    if isinstance(content, dict):
                        if content.get("type") in {"output_text", "text"} and content.get("text"):
                            text = content["text"]
                            break
                        if isinstance(content.get("text"), str):
                            text = content["text"]
                            break
                if text:
                    break
        if not text:
            raise RuntimeError(f"Responses API returned no structured text payload: {payload}")
        return json.loads(text)


class AnthropicJSONClient(BaseJSONClient):
    def __init__(self, model: str | None = None) -> None:
        super().__init__(
            model=model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-0"),
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available():
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        body = {
            "model": self.model,
            "max_tokens": 2048,
            "system": "Return the answer by calling the emit_json tool exactly once.",
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(prompt),
                }
            ],
            "tools": [
                {
                    "name": "emit_json",
                    "description": f"Return JSON matching the schema for {name}.",
                    "input_schema": schema,
                }
            ],
            "tool_choice": {
                "type": "tool",
                "name": "emit_json",
            },
        }
        payload = self._post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            body=body,
        )
        for item in payload.get("content", []) or []:
            if item.get("type") == "tool_use" and item.get("name") == "emit_json":
                tool_input = item.get("input", {})
                if isinstance(tool_input, dict):
                    return tool_input
        raise RuntimeError(f"Anthropic API returned no tool_use JSON payload: {payload}")


class GeminiJSONClient(BaseJSONClient):
    def __init__(self, model: str | None = None) -> None:
        super().__init__(
            model=model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=os.environ.get("GEMINI_API_KEY", ""),
        )

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available():
            raise RuntimeError("GEMINI_API_KEY is not set")

        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": json.dumps(prompt),
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self._sanitize_schema(schema),
            },
        }
        payload = self._post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            body=body,
        )
        for candidate in payload.get("candidates", []) or []:
            content = candidate.get("content", {})
            for part in content.get("parts", []) or []:
                text = part.get("text")
                if text:
                    return json.loads(text)
        raise RuntimeError(f"Gemini API returned no JSON text payload: {payload}")

    def _sanitize_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        def convert(node: Any) -> Any:
            if isinstance(node, list):
                return [convert(item) for item in node]
            if not isinstance(node, dict):
                return node

            converted: Dict[str, Any] = {}
            node_type = node.get("type")
            if node_type:
                converted["type"] = str(node_type).upper()

            if "description" in node and isinstance(node["description"], str):
                converted["description"] = node["description"]

            if node_type == "object":
                properties = node.get("properties", {}) or {}
                converted["properties"] = {
                    key: convert(value)
                    for key, value in properties.items()
                }
                if "required" in node:
                    converted["required"] = list(node.get("required", []))
                if "propertyOrdering" in node:
                    converted["propertyOrdering"] = list(node.get("propertyOrdering", []))
                else:
                    converted["propertyOrdering"] = list(properties.keys())
                return converted

            if node_type == "array":
                items = node.get("items")
                if items is not None:
                    converted["items"] = convert(items)
                return converted

            if "enum" in node:
                converted["enum"] = list(node["enum"])
            if "format" in node and isinstance(node["format"], str):
                converted["format"] = node["format"]
            if "nullable" in node:
                converted["nullable"] = bool(node["nullable"])
            return converted

        sanitized = convert(schema)
        if not isinstance(sanitized, dict):
            raise RuntimeError("Gemini schema sanitizer produced invalid output")
        return sanitized


class OllamaJSONClient(BaseJSONClient):
    def __init__(self, model: str | None = None) -> None:
        super().__init__(
            model=model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            api_key="local",
            timeout_seconds=int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120")),
            max_retries=int(os.environ.get("OLLAMA_MAX_RETRIES", "1")),
        )
        self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

    def available(self) -> bool:
        return True

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON that matches the requested schema. "
                        "Do not include markdown, commentary, or extra keys."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "name": name,
                            "prompt": prompt,
                        }
                    ),
                },
            ],
        }
        payload = self._post_json(
            f"{self.base_url}/api/chat",
            headers={"Content-Type": "application/json"},
            body=body,
        )
        message = payload.get("message", {}) or {}
        text = message.get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"Ollama API returned no JSON message payload: {payload}")
        return json.loads(text)


def make_json_client(provider: str | None = None, model: str | None = None) -> BaseJSONClient:
    selected_provider = (provider or os.environ.get("LLM_PROVIDER", "openai")).strip().lower()
    if selected_provider == "openai":
        return OpenAIJSONClient(model=model)
    if selected_provider == "anthropic":
        return AnthropicJSONClient(model=model)
    if selected_provider == "gemini":
        return GeminiJSONClient(model=model)
    if selected_provider == "ollama":
        return OllamaJSONClient(model=model)
    raise ValueError(f"Unsupported LLM provider: {selected_provider}")


class ResponsesJSONClient(BaseJSONClient):
    def __init__(self, model: str | None = None, provider: str | None = None) -> None:
        self.delegate = make_json_client(provider=provider, model=model)
        super().__init__(
            model=self.delegate.model,
            api_key=self.delegate.api_key,
            timeout_seconds=self.delegate.timeout_seconds,
            max_retries=self.delegate.max_retries,
        )

    def available(self) -> bool:
        return self.delegate.available()

    def complete_json(self, *, name: str, schema: Dict[str, Any], prompt: Dict[str, Any]) -> Dict[str, Any]:
        return self.delegate.complete_json(name=name, schema=schema, prompt=prompt)


class LLMBasedHypothesizer:
    def __init__(self, model: str | None = None, provider: str | None = None) -> None:
        self.client = ResponsesJSONClient(model=model, provider=provider)

    def available(self) -> bool:
        return self.client.available()

    def rank(
        self,
        detection: Dict[str, Any],
        target_deployment: str,
        knowledge_context: Dict[str, Any] | None = None,
    ) -> List[Hypothesis]:
        prompt = {
            "task": "Rank likely incident root-cause hypotheses from detector output.",
            "target_deployment": target_deployment,
            "detection": detection,
            "system_knowledge": knowledge_context or {},
            "requirements": {
                "max_hypotheses": 3,
                "fields": [
                    "id",
                    "title",
                    "suspected_service",
                    "category",
                    "confidence",
                    "rationale",
                    "validation_plan",
                ],
            },
        }
        parsed = self.client.complete_json(
            name="hypotheses",
            schema={
                "type": "object",
                "properties": {
                    "hypotheses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "suspected_service": {"type": "string"},
                                "category": {"type": "string"},
                                "confidence": {"type": "number"},
                                "rationale": {"type": "string"},
                                "validation_plan": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "id",
                                "title",
                                "suspected_service",
                                "category",
                                "confidence",
                                "rationale",
                                "validation_plan",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["hypotheses"],
                "additionalProperties": False,
            },
            prompt=prompt,
        )
        rows = parsed.get("hypotheses", [])
        return [Hypothesis(**row) for row in rows]
