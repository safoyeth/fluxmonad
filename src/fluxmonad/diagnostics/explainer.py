from typing import List
from fluxmonad.plan.node import Node


def build_plan_trace(node: Node) -> List[str]:
    """Собирает цепочку узлов от корня (Source) к текущему узлу."""
    steps: List[str] = []
    current: Node | None = node
    while current is not None:
        steps.append(current.explain_step())
        current = current.parent
    steps.reverse()
    return steps


def format_explain(node: Node) -> str:
    """Форматирует визуальный граф выполнения для explain()."""
    steps = build_plan_trace(node)
    header = "Flux execution plan\n"
    body = "\n  ↓\n".join(steps)
    return header + body