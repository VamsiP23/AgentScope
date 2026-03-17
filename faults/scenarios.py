from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .common import (
    ANN_PREFIX,
    FaultContext,
    get_annotation,
    get_replicas,
    remove_annotation,
    run_kubectl,
    set_annotation,
)


@dataclass(frozen=True)
class FaultScenario:
    name: str

    def apply(self, ctx: FaultContext) -> str:
        raise NotImplementedError

    def revert(self, ctx: FaultContext) -> str:
        raise NotImplementedError


class ServiceOutage(FaultScenario):
    def __init__(self) -> None:
        super().__init__("service_outage")

    def apply(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "checkoutservice"
        key = f"{ANN_PREFIX}/original-replicas"
        current = get_replicas(ctx.namespace, deploy)
        set_annotation(ctx.namespace, deploy, key, current)
        run_kubectl(["scale", "deployment", deploy, "-n", ctx.namespace, "--replicas=0"])
        return f"Scaled deployment/{deploy} from {current} to 0 replicas."

    def revert(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "checkoutservice"
        key = f"{ANN_PREFIX}/original-replicas"
        original = get_annotation(ctx.namespace, deploy, key) or "1"
        run_kubectl(["scale", "deployment", deploy, "-n", ctx.namespace, f"--replicas={original}"])
        remove_annotation(ctx.namespace, deploy, key)
        return f"Restored deployment/{deploy} replicas to {original}."


class DependencyOutage(FaultScenario):
    def __init__(self) -> None:
        super().__init__("dependency_outage")

    def apply(self, ctx: FaultContext) -> str:
        outage = ServiceOutage()
        return outage.apply(FaultContext(namespace=ctx.namespace, target="redis-cart", latency=ctx.latency))

    def revert(self, ctx: FaultContext) -> str:
        outage = ServiceOutage()
        return outage.revert(FaultContext(namespace=ctx.namespace, target="redis-cart", latency=ctx.latency))


class LatencySpike(FaultScenario):
    def __init__(self) -> None:
        super().__init__("latency_spike")

    def apply(self, ctx: FaultContext) -> str:
        deploy = "productcatalogservice"
        key = f"{ANN_PREFIX}/original-extra-latency"
        current = run_kubectl(
            [
                "get",
                "deployment",
                deploy,
                "-n",
                ctx.namespace,
                "-o",
                "jsonpath={.spec.template.spec.containers[?(@.name=='server')].env[?(@.name=='EXTRA_LATENCY')].value}",
            ],
            capture=True,
        )
        if not current:
            current = "__unset__"
        set_annotation(ctx.namespace, deploy, key, current)
        run_kubectl(["set", "env", f"deployment/{deploy}", "-n", ctx.namespace, f"EXTRA_LATENCY={ctx.latency}"])
        return f"Set EXTRA_LATENCY={ctx.latency} on deployment/{deploy}."

    def revert(self, ctx: FaultContext) -> str:
        deploy = "productcatalogservice"
        key = f"{ANN_PREFIX}/original-extra-latency"
        original = get_annotation(ctx.namespace, deploy, key)
        if not original or original == "__unset__":
            run_kubectl(["set", "env", f"deployment/{deploy}", "-n", ctx.namespace, "EXTRA_LATENCY-"])
            message = f"Unset EXTRA_LATENCY on deployment/{deploy}."
        else:
            run_kubectl(["set", "env", f"deployment/{deploy}", "-n", ctx.namespace, f"EXTRA_LATENCY={original}"])
            message = f"Restored EXTRA_LATENCY={original} on deployment/{deploy}."
        remove_annotation(ctx.namespace, deploy, key)
        return message


class CpuPressure(FaultScenario):
    def __init__(self) -> None:
        super().__init__("cpu_pressure")

    def _signal(self, ctx: FaultContext, sig: str) -> None:
        pod = run_kubectl(
            ["get", "pods", "-n", ctx.namespace, "-l", "app=productcatalogservice", "-o", "jsonpath={.items[0].metadata.name}"],
            capture=True,
        )
        if not pod:
            raise RuntimeError(f"No productcatalogservice pod found in namespace {ctx.namespace}")
        run_kubectl(["exec", "-n", ctx.namespace, pod, "-c", "server", "--", "kill", f"-{sig}", "1"])

    def apply(self, ctx: FaultContext) -> str:
        self._signal(ctx, "USR1")
        return "Triggered CPU pressure mode on productcatalogservice (USR1)."

    def revert(self, ctx: FaultContext) -> str:
        self._signal(ctx, "USR2")
        return "Reverted CPU pressure mode on productcatalogservice (USR2)."


SCENARIOS: Dict[str, FaultScenario] = {
    "service_outage": ServiceOutage(),
    "dependency_outage": DependencyOutage(),
    "latency_spike": LatencySpike(),
    "cpu_pressure": CpuPressure(),
}
