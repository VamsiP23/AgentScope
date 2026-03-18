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


class CpuThrottling(FaultScenario):
    def __init__(self) -> None:
        super().__init__("cpu_throttling")

    def apply(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "productcatalogservice"
        limit_key = f"{ANN_PREFIX}/original-cpu-limit"
        request_key = f"{ANN_PREFIX}/original-cpu-request"
        current_limit = run_kubectl(
            [
                "get",
                "deployment",
                deploy,
                "-n",
                ctx.namespace,
                "-o",
                "jsonpath={.spec.template.spec.containers[0].resources.limits.cpu}",
            ],
            capture=True,
        )
        current_request = run_kubectl(
            [
                "get",
                "deployment",
                deploy,
                "-n",
                ctx.namespace,
                "-o",
                "jsonpath={.spec.template.spec.containers[0].resources.requests.cpu}",
            ],
            capture=True,
        )
        set_annotation(ctx.namespace, deploy, limit_key, current_limit or "__unset__")
        set_annotation(ctx.namespace, deploy, request_key, current_request or "__unset__")
        run_kubectl(
            [
                "patch",
                "deployment",
                deploy,
                "-n",
                ctx.namespace,
                "--type=strategic",
                "-p",
                (
                    '{"spec":{"template":{"spec":{"containers":[{"name":"server","resources":'
                    f'{{"requests":{{"cpu":"{ctx.cpu_request}"}},"limits":{{"cpu":"{ctx.cpu_limit}"}}}}'
                    '}]}}}}'
                ),
            ]
        )
        return (
            f"Patched deployment/{deploy} CPU request={ctx.cpu_request} "
            f"limit={ctx.cpu_limit}."
        )

    def revert(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "productcatalogservice"
        limit_key = f"{ANN_PREFIX}/original-cpu-limit"
        request_key = f"{ANN_PREFIX}/original-cpu-request"
        original_limit = get_annotation(ctx.namespace, deploy, limit_key) or "__unset__"
        original_request = get_annotation(ctx.namespace, deploy, request_key) or "__unset__"

        limit_fragment = "null" if original_limit == "__unset__" else f'"{original_limit}"'
        request_fragment = "null" if original_request == "__unset__" else f'"{original_request}"'
        run_kubectl(
            [
                "patch",
                "deployment",
                deploy,
                "-n",
                ctx.namespace,
                "--type=strategic",
                "-p",
                (
                    '{"spec":{"template":{"spec":{"containers":[{"name":"server","resources":'
                    f'{{"requests":{{"cpu":{request_fragment}}},"limits":{{"cpu":{limit_fragment}}}}}'
                    '}]}}}}'
                ),
            ]
        )
        remove_annotation(ctx.namespace, deploy, limit_key)
        remove_annotation(ctx.namespace, deploy, request_key)
        message = (
            f"Restored deployment/{deploy} CPU request={original_request} "
            f"limit={original_limit}."
        )
        return message


class ReplicaReductionUnderLoad(FaultScenario):
    def __init__(self) -> None:
        super().__init__("replica_reduction_under_load")

    def apply(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "frontend"
        key = f"{ANN_PREFIX}/original-replicas"
        current = get_replicas(ctx.namespace, deploy)
        set_annotation(ctx.namespace, deploy, key, current)
        run_kubectl(
            ["scale", "deployment", deploy, "-n", ctx.namespace, f"--replicas={ctx.replicas}"]
        )
        return f"Scaled deployment/{deploy} from {current} to {ctx.replicas} replicas."

    def revert(self, ctx: FaultContext) -> str:
        deploy = ctx.target or "frontend"
        key = f"{ANN_PREFIX}/original-replicas"
        original = get_annotation(ctx.namespace, deploy, key) or "1"
        run_kubectl(["scale", "deployment", deploy, "-n", ctx.namespace, f"--replicas={original}"])
        remove_annotation(ctx.namespace, deploy, key)
        return f"Restored deployment/{deploy} replicas to {original}."


SCENARIOS: Dict[str, FaultScenario] = {
    "service_outage": ServiceOutage(),
    "dependency_outage": DependencyOutage(),
    "cpu_throttling": CpuThrottling(),
    "replica_reduction_under_load": ReplicaReductionUnderLoad(),
}
