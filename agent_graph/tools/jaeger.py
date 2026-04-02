from __future__ import annotations

import json
import socket
import time
from collections import Counter, defaultdict
from http.client import RemoteDisconnected
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


class JaegerTools:
    def __init__(self, jaeger_url: str) -> None:
        self.jaeger_url = jaeger_url.rstrip("/")
        self.timeout_seconds = 20
        self.max_retries = 4
        self.retryable_messages = (
            "remote end closed connection without response",
            "connection reset",
            "connection aborted",
            "timed out",
            "timeout",
            "temporarily unavailable",
        )

    def list_services(self) -> Dict[str, Any]:
        payload = self._fetch_json("/api/services")
        services = list(payload.get("data", []) or [])
        return {
            "service_count": len(services),
            "services": services,
        }

    def get_entry_point_traces(self, service: str, lookback_minutes: int = 5, limit: int = 20) -> Dict[str, Any]:
        if not self._service_present(service):
            return self._missing_service(service)

        traces = self._search_traces(service, lookback_minutes=lookback_minutes, limit=limit)
        application_traces = self._application_traces(traces)
        durations = [trace["total_duration_ms"] for trace in application_traces]
        slowest_trace = max(application_traces, key=lambda trace: trace["total_duration_ms"], default=None)
        bottleneck = self._find_common_bottleneck(application_traces)
        return {
            "service": service,
            "service_present": True,
            "trace_quality": self._trace_quality(application_traces, traces),
            "raw_trace_count": len(traces),
            "application_trace_count": len(application_traces),
            "probe_trace_count_filtered": max(0, len(traces) - len(application_traces)),
            "trace_count": len(application_traces),
            "p50_duration_ms": self._percentile(durations, 50),
            "p95_duration_ms": self._percentile(durations, 95),
            "p99_duration_ms": self._percentile(durations, 99),
            "slowest_trace": slowest_trace,
            "common_bottleneck": bottleneck,
            "summary": self._entry_point_summary(service, application_traces, bottleneck),
        }

    def get_dependency_health(
        self,
        service: str,
        lookback_minutes: int = 5,
        limit: int = 50,
        slow_threshold_ms: float = 500.0,
    ) -> Dict[str, Any]:
        if not self._service_present(service):
            return self._missing_service(service)

        traces = self._search_traces(service, lookback_minutes=lookback_minutes, limit=limit)
        application_traces = self._application_traces(traces)
        total = len(application_traces)
        error_traces = [trace for trace in application_traces if trace["has_error"]]
        slow_traces = [trace for trace in application_traces if trace["total_duration_ms"] >= slow_threshold_ms]
        error_types = self._extract_error_types(application_traces)
        return {
            "service": service,
            "service_present": True,
            "trace_quality": self._trace_quality(application_traces, traces),
            "raw_trace_count": len(traces),
            "application_trace_count": total,
            "probe_trace_count_filtered": max(0, len(traces) - total),
            "total_traces": total,
            "error_rate": (len(error_traces) / total) if total else 0.0,
            "slow_rate": (len(slow_traces) / total) if total else 0.0,
            "error_types": error_types,
            "health_classification": self._classify_health(bool(error_traces), bool(slow_traces), total > 0),
            "summary": self._dependency_health_summary(service, total, error_traces, slow_traces, error_types),
        }

    def get_call_chain(self, trace_id: str) -> Dict[str, Any]:
        raw_trace = self._fetch_trace(trace_id)
        parsed = self._parse_trace(raw_trace)
        return {
            "trace_id": trace_id,
            "service": parsed["service"],
            "total_duration_ms": parsed["total_duration_ms"],
            "has_error": parsed["has_error"],
            "error_types": parsed["error_types"],
            "hops": parsed["hops"],
            "summary": (
                f"trace {trace_id} spans {len(parsed['hops'])} hops over {parsed['total_duration_ms']:.1f} ms"
                if parsed["hops"]
                else f"trace {trace_id} contains no parsed hops"
            ),
        }

    def get_service_trace_summary(self, service: str, lookback_minutes: int = 5, limit: int = 20) -> Dict[str, Any]:
        try:
            entry = self.get_entry_point_traces(service, lookback_minutes=lookback_minutes, limit=limit)
        except Exception as exc:
            return {
                "service": service,
                "lookback_minutes": lookback_minutes,
                "trace_quality": "unavailable",
                "trace_count": 0,
                "entry_point": service,
                "slowest_trace_id": "",
                "call_chain": [],
                "bottleneck_service": "",
                "bottleneck_pct_of_total": 0.0,
                "baseline_p99_ms": 0.0,
                "deviation_factor": 0.0,
                "error_spans": [],
                "observability_error": True,
                "observability_status": "jaeger_unavailable",
                "error": str(exc),
            }

        slowest_trace = entry.get("slowest_trace") or {}
        trace_id = str(slowest_trace.get("trace_id", "") or "")
        if trace_id:
            try:
                call_chain = self.get_trace_detail(trace_id)
            except Exception as exc:
                call_chain = {
                    "trace_id": trace_id,
                    "hops": [],
                    "error": str(exc),
                }
        else:
            call_chain = {
                "trace_id": "",
                "hops": [],
                "error": None,
            }

        error_spans = [
            {
                "service": hop.get("service", ""),
                "operation": hop.get("operation", ""),
                "duration_ms": hop.get("duration_ms", 0.0),
                "error_message": hop.get("error_message", ""),
            }
            for hop in call_chain.get("hops", []) or []
            if hop.get("error", False)
        ]
        bottleneck = entry.get("common_bottleneck") or {}
        baseline = {
            "baseline_p99_ms": 0.0,
            "deviation_factor": 0.0,
            "error": None,
        }
        bottleneck_service = str(bottleneck.get("service", "") or "")
        bottleneck_duration_ms = float(bottleneck.get("avg_duration_ms", 0.0) or 0.0)
        if bottleneck_service and bottleneck_duration_ms > 0:
            baseline = self.compare_baseline(
                bottleneck_service,
                current_ms=bottleneck_duration_ms,
                lookback_minutes=60,
                limit=100,
            )

        return {
            "service": service,
            "lookback_minutes": lookback_minutes,
            "trace_quality": entry.get("trace_quality", "missing"),
            "trace_count": entry.get("trace_count", 0),
            "entry_point": slowest_trace.get("service") or entry.get("service") or service,
            "slowest_trace_id": trace_id,
            "call_chain": call_chain.get("hops", []) or [],
            "bottleneck_service": bottleneck_service,
            "bottleneck_pct_of_total": bottleneck.get("pct_of_total", 0.0),
            "baseline_p99_ms": float(baseline.get("baseline_p99_ms", 0.0) or 0.0),
            "deviation_factor": float(baseline.get("deviation_factor", 0.0) or 0.0),
            "error_spans": error_spans,
            "observability_error": bool(
                entry.get("observability_error", False) or call_chain.get("observability_error", False)
            ),
            "observability_status": (
                str(entry.get("observability_status", "") or call_chain.get("observability_status", ""))
            ),
            "error": entry.get("error") or call_chain.get("error") or baseline.get("error"),
        }

    def get_dependency_trace_summary(
        self,
        service: str,
        entry_service: str = "frontend",
        lookback_minutes: int = 5,
        limit: int = 20,
    ) -> Dict[str, Any]:
        try:
            if not self._service_present(entry_service):
                missing = self._missing_service(entry_service)
                return {
                    "service": service,
                    "entry_service": entry_service,
                    "trace_quality": missing.get("trace_quality", "missing"),
                    "raw_trace_count": 0,
                    "application_trace_count": 0,
                    "focus_trace_count": 0,
                    "trace_count": 0,
                    "downstream_candidates": [],
                    "bottleneck_service": "",
                    "bottleneck_pct_of_total": 0.0,
                    "call_chain": [],
                    "error_spans": [],
                    "observability_error": False,
                    "observability_status": "",
                    "error": None,
                    "summary": f"{entry_service} is not present in Jaeger service discovery",
                }

            raw_traces = self._search_traces(entry_service, lookback_minutes=lookback_minutes, limit=limit)
            application_traces = self._application_traces(raw_traces)
        except Exception as exc:
            return {
                "service": service,
                "entry_service": entry_service,
                "trace_quality": "unavailable",
                "raw_trace_count": 0,
                "application_trace_count": 0,
                "focus_trace_count": 0,
                "trace_count": 0,
                "downstream_candidates": [],
                "bottleneck_service": "",
                "bottleneck_pct_of_total": 0.0,
                "call_chain": [],
                "error_spans": [],
                "observability_error": True,
                "observability_status": "jaeger_unavailable",
                "error": str(exc),
                "summary": f"trace data unavailable from Jaeger while analyzing {service} via {entry_service}",
            }

        relevant_traces = [trace for trace in application_traces if self._trace_contains_service(trace, service)]
        downstream_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "service": "",
                "count": 0,
                "total_duration_ms": 0.0,
                "total_pct_of_total": 0.0,
            }
        )
        error_spans: List[Dict[str, Any]] = []

        for trace in relevant_traces:
            for hop in trace.get("hops", []) or []:
                hop_service = self._normalize_service_name(str(hop.get("service", "")))
                if hop_service != self._normalize_service_name(service):
                    continue
                downstream_service = self._normalize_dependency_name(str(hop.get("peer_service", "")))
                if not downstream_service or downstream_service == hop_service:
                    continue
                bucket = downstream_stats[downstream_service]
                bucket["service"] = downstream_service
                bucket["count"] += 1
                bucket["total_duration_ms"] += float(hop.get("duration_ms", 0.0) or 0.0)
                bucket["total_pct_of_total"] += float(hop.get("pct_of_total", 0.0) or 0.0)
                if bool(hop.get("error", False)):
                    error_spans.append(
                        {
                            "service": downstream_service,
                            "operation": str(hop.get("operation", "")),
                            "duration_ms": float(hop.get("duration_ms", 0.0) or 0.0),
                            "error_message": str(hop.get("error_message", "")),
                        }
                    )

        downstream_candidates = [
            {
                "service": item["service"],
                "count": item["count"],
                "avg_duration_ms": (item["total_duration_ms"] / item["count"]) if item["count"] else 0.0,
                "avg_pct_of_total": (item["total_pct_of_total"] / item["count"]) if item["count"] else 0.0,
            }
            for item in downstream_stats.values()
            if item["service"]
        ]
        downstream_candidates.sort(
            key=lambda item: (float(item.get("avg_pct_of_total", 0.0) or 0.0), float(item.get("avg_duration_ms", 0.0) or 0.0)),
            reverse=True,
        )

        slowest_relevant = max(relevant_traces, key=lambda trace: trace.get("total_duration_ms", 0.0), default=None)
        focus_path = self._focus_service_path(slowest_relevant, service) if slowest_relevant else []
        trace_quality = self._dependency_trace_quality(raw_traces, application_traces, relevant_traces, downstream_candidates)
        bottleneck = downstream_candidates[0] if downstream_candidates else {}

        return {
            "service": service,
            "entry_service": entry_service,
            "trace_quality": trace_quality,
            "raw_trace_count": len(raw_traces),
            "application_trace_count": len(application_traces),
            "focus_trace_count": len(relevant_traces),
            "trace_count": len(relevant_traces),
            "downstream_candidates": downstream_candidates[:5],
            "bottleneck_service": str(bottleneck.get("service", "") or ""),
            "bottleneck_pct_of_total": float(bottleneck.get("avg_pct_of_total", 0.0) or 0.0),
            "call_chain": focus_path,
            "error_spans": error_spans[:5],
            "observability_error": False,
            "observability_status": "",
            "error": None,
            "summary": self._dependency_trace_summary_text(
                service=service,
                entry_service=entry_service,
                relevant_trace_count=len(relevant_traces),
                downstream_candidates=downstream_candidates[:3],
            ),
        }

    def get_trace_detail(self, trace_id: str) -> Dict[str, Any]:
        try:
            detail = self.get_call_chain(trace_id)
        except Exception as exc:
            return {
                "trace_id": trace_id,
                "service": "",
                "total_duration_ms": 0.0,
                "has_error": False,
                "error_types": [],
                "hops": [],
                "summary": f"failed to fetch trace {trace_id}",
                "observability_error": True,
                "observability_status": "jaeger_unavailable",
                "error": str(exc),
            }
        detail["error"] = None
        detail["observability_error"] = False
        detail["observability_status"] = ""
        return detail

    def compare_baseline(
        self,
        service: str,
        current_ms: float,
        lookback_minutes: int = 60,
        limit: int = 100,
    ) -> Dict[str, Any]:
        if not self._service_present(service):
            return self._missing_service(service, extra={"current_ms": current_ms})

        traces = self._search_traces(service, lookback_minutes=lookback_minutes, limit=limit)
        application_traces = self._application_traces(traces)
        durations = [trace["total_duration_ms"] for trace in application_traces]
        baseline_p50 = self._percentile(durations, 50)
        baseline_p99 = self._percentile(durations, 99)
        deviation_factor = (current_ms / baseline_p99) if baseline_p99 > 0 else 0.0
        is_anomalous = bool(baseline_p99 > 0 and current_ms > baseline_p99 * 1.5)
        return {
            "service": service,
            "service_present": True,
            "trace_quality": self._trace_quality(application_traces, traces),
            "raw_trace_count": len(traces),
            "application_trace_count": len(application_traces),
            "probe_trace_count_filtered": max(0, len(traces) - len(application_traces)),
            "current_ms": current_ms,
            "baseline_p50_ms": baseline_p50,
            "baseline_p99_ms": baseline_p99,
            "deviation_factor": deviation_factor,
            "is_anomalous": is_anomalous,
            "summary": (
                f"{service} current={current_ms:.1f}ms baseline_p99={baseline_p99:.1f}ms"
                if baseline_p99 > 0
                else f"no baseline traces available for {service}"
            ),
        }

    def _fetch_json(self, path: str) -> Dict[str, Any]:
        url = f"{self.jaeger_url}{path}"
        backoff_seconds = 0.5
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(url, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Jaeger HTTP {exc.code}: {detail}") from exc
            except Exception as exc:
                last_error = exc
                if self._is_retryable_exception(exc) and attempt < self.max_retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue
                raise RuntimeError(self._observability_error_message(exc)) from exc

        raise RuntimeError(self._observability_error_message(last_error))

    def _search_traces(self, service: str, lookback_minutes: int, limit: int) -> List[Dict[str, Any]]:
        params = urlencode(
            {
                "service": service,
                "limit": limit,
                "lookback": f"{max(1, lookback_minutes)}m",
            }
        )
        payload = self._fetch_json(f"/api/traces?{params}")
        return list(payload.get("data", []) or [])

    def _fetch_trace(self, trace_id: str) -> Dict[str, Any]:
        payload = self._fetch_json(f"/api/traces/{trace_id}")
        traces = list(payload.get("data", []) or [])
        if not traces:
            return {}
        return traces[0]

    def _service_present(self, service: str) -> bool:
        try:
            return service in (self.list_services().get("services", []) or [])
        except Exception as exc:
            raise RuntimeError(self._observability_error_message(exc)) from exc

    def _missing_service(self, service: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "service": service,
            "service_present": False,
            "trace_quality": "missing",
            "trace_count": 0,
            "summary": f"{service} is not present in Jaeger service discovery",
        }
        if extra:
            payload.update(extra)
        return payload

    def _application_traces(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed: List[Dict[str, Any]] = []
        for trace in traces:
            if self._is_probe_or_health_trace(trace):
                continue
            parsed.append(self._parse_trace(trace))
        return parsed

    def _parse_trace(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        spans = list(trace.get("spans", []) or [])
        processes = dict(trace.get("processes", {}) or {})
        root_span = self._root_span(spans)
        total_duration_ms = self._duration_ms(root_span.get("duration", 0) if root_span else 0)
        if spans:
            total_duration_ms = max(
                total_duration_ms,
                max(self._duration_ms(span.get("duration", 0)) for span in spans),
            )
        hops: List[Dict[str, Any]] = []
        error_types: List[str] = []
        for span in sorted(spans, key=lambda item: int(item.get("startTime", 0))):
            service_name = self._service_name(processes, span.get("processID", ""))
            duration_ms = self._duration_ms(span.get("duration", 0))
            error = self._span_has_error(span)
            error_message = self._span_error_message(span)
            peer_service = self._span_peer_service(span)
            if error and error_message:
                error_types.append(error_message)
            hop = {
                "span_id": span.get("spanID", ""),
                "service": service_name,
                "operation": span.get("operationName", ""),
                "duration_ms": duration_ms,
                "pct_of_total": min((duration_ms / total_duration_ms), 1.0) if total_duration_ms > 0 else 0.0,
                "error": error,
                "error_message": error_message,
            }
            if peer_service:
                hop["peer_service"] = peer_service
            hops.append(hop)
        return {
            "trace_id": trace.get("traceID", ""),
            "service": self._service_name(processes, root_span.get("processID", "")) if root_span else "",
            "total_duration_ms": total_duration_ms,
            "has_error": any(hop["error"] for hop in hops),
            "error_types": sorted({item for item in error_types if item}),
            "hops": hops,
        }

    def _root_span(self, spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        span_ids = {str(span.get("spanID", "")) for span in spans}
        for span in spans:
            refs = span.get("references", []) or []
            if not refs:
                return span
            parent_ids = {str(ref.get("spanID", "")) for ref in refs if str(ref.get("refType", "")) == "CHILD_OF"}
            if not parent_ids.intersection(span_ids):
                return span
        return spans[0] if spans else None

    def _is_probe_or_health_trace(self, trace: Dict[str, Any]) -> bool:
        spans = list(trace.get("spans", []) or [])
        if not spans:
            return True
        meaningful_spans = 0
        for span in spans:
            tags = {str(tag.get("key", "")): str(tag.get("value", "")) for tag in span.get("tags", []) or []}
            user_agent = tags.get("user_agent.original", "").lower()
            http_target = tags.get("http.target", "")
            operation = str(span.get("operationName", "")).lower()
            if "kube-probe" in user_agent:
                continue
            if http_target == "/_healthz":
                continue
            if "grpc.health" in operation or "healthcheck" in operation:
                continue
            if "traceservice/export" in operation:
                continue
            meaningful_spans += 1
        return meaningful_spans == 0

    def _find_common_bottleneck(self, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        service_totals: Dict[str, List[float]] = defaultdict(list)
        for trace in traces:
            total = trace["total_duration_ms"]
            for hop in trace["hops"]:
                service = hop["service"]
                if not service or service == trace["service"]:
                    continue
                service_totals[service].append(hop["duration_ms"] / total if total > 0 else 0.0)
        if not service_totals:
            return {}
        best_service = max(service_totals.items(), key=lambda item: sum(item[1]) / len(item[1]))[0]
        ratios = service_totals[best_service]
        avg_ratio = sum(ratios) / len(ratios)
        avg_durations: List[float] = []
        for trace in traces:
            for hop in trace["hops"]:
                if hop["service"] == best_service:
                    avg_durations.append(hop["duration_ms"])
        return {
            "service": best_service,
            "avg_duration_ms": (sum(avg_durations) / len(avg_durations)) if avg_durations else 0.0,
            "pct_of_total": avg_ratio,
        }

    def _extract_error_types(self, traces: List[Dict[str, Any]]) -> List[str]:
        counts: Counter[str] = Counter()
        for trace in traces:
            for item in trace["error_types"]:
                counts[item] += 1
        return [name for name, _ in counts.most_common(5)]

    def _classify_health(self, has_errors: bool, has_slowness: bool, has_data: bool) -> str:
        if not has_data:
            return "unknown"
        if has_errors and has_slowness:
            return "both"
        if has_errors:
            return "erroring"
        if has_slowness:
            return "slow"
        return "healthy"

    def _trace_quality(self, application_traces: List[Dict[str, Any]], raw_traces: List[Dict[str, Any]]) -> str:
        if not raw_traces:
            return "missing"
        if not application_traces:
            return "weak"
        if any(self._trace_has_invalid_percentages(trace) for trace in application_traces):
            return "weak"
        return "good"

    def _dependency_trace_quality(
        self,
        raw_traces: List[Dict[str, Any]],
        application_traces: List[Dict[str, Any]],
        relevant_traces: List[Dict[str, Any]],
        downstream_candidates: List[Dict[str, Any]],
    ) -> str:
        if not raw_traces:
            return "missing"
        if not application_traces:
            return "weak"
        if not relevant_traces:
            return "weak"
        if any(self._trace_has_invalid_percentages(trace) for trace in relevant_traces):
            return "weak"
        if not downstream_candidates:
            return "weak"
        return "good"

    def _trace_has_invalid_percentages(self, trace: Dict[str, Any]) -> bool:
        for hop in trace.get("hops", []) or []:
            pct = float(hop.get("pct_of_total", 0.0) or 0.0)
            if pct < 0.0 or pct > 1.0:
                return True
        return False

    def _is_retryable_exception(self, exc: Exception) -> bool:
        if isinstance(exc, (RemoteDisconnected, ConnectionResetError, TimeoutError, socket.timeout)):
            return True
        if isinstance(exc, URLError):
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (RemoteDisconnected, ConnectionResetError, TimeoutError, socket.timeout)):
                return True
        message = str(exc).lower()
        return any(marker in message for marker in self.retryable_messages)

    def _observability_error_message(self, exc: Exception | None) -> str:
        detail = str(exc) if exc is not None else "unknown Jaeger error"
        return f"trace data unavailable from Jaeger: {detail}"

    def _duration_ms(self, duration_microseconds: Any) -> float:
        try:
            return float(duration_microseconds) / 1000.0
        except Exception:
            return 0.0

    def _percentile(self, values: List[float], percentile: int) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(0, min(len(ordered) - 1, round((percentile / 100.0) * (len(ordered) - 1))))
        return float(ordered[rank])

    def _service_name(self, processes: Dict[str, Any], process_id: str) -> str:
        process = dict(processes.get(process_id, {}) or {})
        service_name = str(process.get("serviceName", ""))
        return service_name

    def _normalize_service_name(self, service: str) -> str:
        return str(service or "").strip().lower()

    def _normalize_dependency_name(self, peer_service: str) -> str:
        value = str(peer_service or "").strip()
        if not value:
            return ""
        value = value.split("/", 1)[0]
        value = value.split(".")[-1]
        cleaned = "".join(ch for ch in value.lower() if ch.isalnum() or ch == "-")
        return cleaned

    def _trace_contains_service(self, trace: Dict[str, Any], service: str) -> bool:
        normalized = self._normalize_service_name(service)
        for hop in trace.get("hops", []) or []:
            if self._normalize_service_name(str(hop.get("service", ""))) == normalized:
                return True
        return self._normalize_service_name(str(trace.get("service", ""))) == normalized

    def _focus_service_path(self, trace: Dict[str, Any], service: str) -> List[Dict[str, Any]]:
        if not trace:
            return []
        normalized = self._normalize_service_name(service)
        focus_hops: List[Dict[str, Any]] = []
        for hop in trace.get("hops", []) or []:
            hop_service = self._normalize_service_name(str(hop.get("service", "")))
            if hop_service != normalized:
                continue
            downstream_service = self._normalize_dependency_name(str(hop.get("peer_service", "")))
            focus_hops.append(
                {
                    "service": hop_service,
                    "downstream_service": downstream_service,
                    "operation": str(hop.get("operation", "")),
                    "duration_ms": float(hop.get("duration_ms", 0.0) or 0.0),
                    "pct_of_total": float(hop.get("pct_of_total", 0.0) or 0.0),
                    "error": bool(hop.get("error", False)),
                    "error_message": str(hop.get("error_message", "")),
                }
            )
        return focus_hops[:8]

    def _span_has_error(self, span: Dict[str, Any]) -> bool:
        for tag in span.get("tags", []) or []:
            key = str(tag.get("key", ""))
            value = str(tag.get("value", "")).lower()
            if key == "error" and value in {"true", "1"}:
                return True
            if key in {"otel.status_code", "status.code"} and value == "error":
                return True
        return False

    def _span_error_message(self, span: Dict[str, Any]) -> str:
        for key in ("error.message", "otel.status_description", "rpc.grpc.status_code", "http.status_code"):
            for tag in span.get("tags", []) or []:
                if str(tag.get("key", "")) == key:
                    value = str(tag.get("value", "")).strip()
                    if value:
                        return value
        return ""

    def _span_peer_service(self, span: Dict[str, Any]) -> str:
        for key in ("peer.service", "rpc.service", "net.peer.name", "db.system"):
            for tag in span.get("tags", []) or []:
                if str(tag.get("key", "")) == key:
                    value = str(tag.get("value", "")).strip()
                    if value:
                        return value
        return ""

    def _entry_point_summary(self, service: str, traces: List[Dict[str, Any]], bottleneck: Dict[str, Any]) -> str:
        if not traces:
            return f"no application traces found for {service}"
        if bottleneck:
            return (
                f"{service} traces point to {bottleneck['service']} as the common bottleneck "
                f"at {bottleneck['pct_of_total'] * 100:.1f}% of total latency"
            )
        return f"{service} has {len(traces)} application traces but no repeated downstream bottleneck"

    def _dependency_trace_summary_text(
        self,
        service: str,
        entry_service: str,
        relevant_trace_count: int,
        downstream_candidates: List[Dict[str, Any]],
    ) -> str:
        if relevant_trace_count <= 0:
            return f"no {entry_service} traces in the current window showed downstream calls from {service}"
        if not downstream_candidates:
            return f"{entry_service} traces include {service}, but no repeated downstream bottleneck was identified beneath it"
        top = downstream_candidates[0]
        return (
            f"{entry_service} traces flowing through {service} most often bottleneck on {top['service']} "
            f"at {float(top.get('avg_pct_of_total', 0.0) or 0.0) * 100:.1f}% of total latency"
        )

    def _dependency_health_summary(
        self,
        service: str,
        total: int,
        error_traces: List[Dict[str, Any]],
        slow_traces: List[Dict[str, Any]],
        error_types: List[str],
    ) -> str:
        if total == 0:
            return f"no application traces found for {service}"
        classification = self._classify_health(bool(error_traces), bool(slow_traces), total > 0)
        top_error = error_types[0] if error_types else "none"
        return (
            f"{service} classified as {classification}; "
            f"errors={len(error_traces)}/{total}, slow={len(slow_traces)}/{total}, top_error={top_error}"
        )
