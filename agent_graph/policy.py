from __future__ import annotations

from typing import List

from agent_graph.reasoning.llm import ResponsesJSONClient
from agent_graph.schemas import EvidenceItem, Hypothesis, PolicyDecision


class Policy:
    def __init__(self, mode: str = "heuristic") -> None:
        self.mode = mode
        self.llm = ResponsesJSONClient()

    def run(self, hypotheses: List[Hypothesis], evidence: List[EvidenceItem]) -> PolicyDecision:
        if self.mode == "llm":
            if not self.llm.available():
                raise RuntimeError("LLM mode requested but OPENAI_API_KEY is not set")
            try:
                return self._run_llm(hypotheses, evidence)
            except Exception as exc:
                raise RuntimeError(f"LLM policy failed: {exc}") from exc
        return self._run_heuristic(hypotheses, evidence)

    def _run_heuristic(self, hypotheses: List[Hypothesis], evidence: List[EvidenceItem]) -> PolicyDecision:
        scores = {hyp.id: hyp.confidence for hyp in hypotheses}
        by_id = {hyp.id: hyp for hyp in hypotheses}
        for item in evidence:
            for hyp_id in item.supports:
                scores[hyp_id] = scores.get(hyp_id, 0.0) + 0.15
            for hyp_id in item.contradicts:
                scores[hyp_id] = scores.get(hyp_id, 0.0) - 0.25
        if not scores:
            return PolicyDecision(
                actionability="monitor",
                confidence=0.0,
                rationale="No hypotheses available to adjudicate.",
                missing_evidence=["detector_summary", "target_service_signals"],
            )

        best_id = max(scores, key=scores.get)
        best = by_id[best_id]
        best_score = max(0.0, min(0.99, scores[best_id]))
        actionability = "act" if best_score >= 0.65 else "monitor"
        rejected = [hyp.id for hyp in hypotheses if hyp.id != best_id]
        return PolicyDecision(
            supported_hypothesis_id=best_id,
            supported_hypothesis={**best.to_dict(), "confidence": best_score},
            actionability=actionability,
            confidence=best_score,
            rationale=(
                f"Selected {best_id} after combining prior confidence with supporting and contradicting evidence."
            ),
            rejected_hypothesis_ids=rejected,
            missing_evidence=[] if actionability == "act" else ["more trace or resource evidence"],
        )

    def _run_llm(self, hypotheses: List[Hypothesis], evidence: List[EvidenceItem]) -> PolicyDecision:
        prompt = {
            "task": "Judge whether the evidence supports one of the root-cause hypotheses strongly enough to act.",
            "hypotheses": [hyp.to_dict() for hyp in hypotheses],
            "evidence": [item.to_dict() for item in evidence],
            "requirements": {
                "choose_supported_hypothesis_id": True,
                "actionability_values": ["act", "monitor"],
                "prefer monitor when evidence is weak or contradictory": True,
            },
        }
        parsed = self.llm.complete_json(
            name="policy_decision",
            schema={
                "type": "object",
                "properties": {
                    "supported_hypothesis_id": {"type": "string"},
                    "actionability": {"type": "string"},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                    "rejected_hypothesis_ids": {"type": "array", "items": {"type": "string"}},
                    "missing_evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "supported_hypothesis_id",
                    "actionability",
                    "confidence",
                    "rationale",
                    "rejected_hypothesis_ids",
                    "missing_evidence",
                ],
                "additionalProperties": False,
            },
            prompt=prompt,
        )
        supported_id = parsed.get("supported_hypothesis_id", "")
        supported = next((hyp for hyp in hypotheses if hyp.id == supported_id), None)
        return PolicyDecision(
            supported_hypothesis_id=supported_id,
            supported_hypothesis=supported.to_dict() if supported else {},
            actionability=str(parsed.get("actionability", "monitor")),
            confidence=float(parsed.get("confidence", 0.0)),
            rationale=str(parsed.get("rationale", "")),
            rejected_hypothesis_ids=list(parsed.get("rejected_hypothesis_ids", [])),
            missing_evidence=list(parsed.get("missing_evidence", [])),
        )
