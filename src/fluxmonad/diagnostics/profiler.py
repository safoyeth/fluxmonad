import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional
from fluxmonad.plan.node import Node


@dataclass
class StepMetric:
    step_description: str
    elapsed_ms: float
    items_processed: int


class ProfileResult:
    def __init__(self, metrics: List[StepMetric], total_time_ms: float, result: List[Any]) -> None:
        self.metrics = metrics
        self.total_time_ms = total_time_ms
        self.result = result

    def summary(self) -> str:
        lines = [f"Pipeline Profile (Total: {self.total_time_ms:.2f} ms):"]
        for idx, m in enumerate(self.metrics, start=1):
            rate = (m.items_processed / (m.elapsed_ms / 1000.0)) if m.elapsed_ms > 0 else 0
            lines.append(
                f"  [{idx}] {m.step_description} -> {m.items_processed} items | "
                f"{m.elapsed_ms:.2f} ms ({rate:.1f} items/s)"
            )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()


def profile_pipeline(node: Node) -> ProfileResult:
    """Выполняет пайплайн с телеметрией каждого узла."""
    # Собираем линейную последовательность узлов
    nodes: List[Node] = []
    curr: Optional[Node] = node
    while curr is not None:
        nodes.append(curr)
        curr = curr.parent
    nodes.reverse()

    metrics: List[StepMetric] = []
    overall_start = time.perf_counter()

    current_data: Iterator[Any] = iter([])

    for step_node in nodes:
        step_start = time.perf_counter()

        if step_node.parent is None:
            # Source узел
            materialized = list(step_node.evaluate())
        else:
            # Создаем временный узел с уже материализованным источником
            from fluxmonad.plan.source import SourceNode
            step_node.parent = SourceNode(current_data)
            materialized = list(step_node.evaluate())

        step_elapsed = (time.perf_counter() - step_start) * 1000.0
        metrics.append(
            StepMetric(
                step_description=step_node.explain_step(),
                elapsed_ms=step_elapsed,
                items_processed=len(materialized),
            )
        )
        current_data = materialized

    overall_total = (time.perf_counter() - overall_start) * 1000.0
    return ProfileResult(metrics=metrics, total_time_ms=overall_total, result=materialized)