from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from agent_graph.schemas import Hypothesis


class LLMBasedHypothesizer:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def available(self) -> bool:
        return bool(self.api_key)

    def rank(
        self,
        detection: Dict[str, Any],
        target_deployment: str,
        knowledge_context: Dict[str, Any] | None = None,
    ) -> List[Hypothesis]:
        if not self.available():
            raise RuntimeError("OPENAI_API_KEY is not set")

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
                    "name": "hypotheses",
                    "schema": {
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
                }
            },
        }
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload.get("output", [])[0].get("content", [])[0].get("text", "{}")
        parsed = json.loads(text)
        rows = parsed.get("hypotheses", [])
        return [Hypothesis(**row) for row in rows]
