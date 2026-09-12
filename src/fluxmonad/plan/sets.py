from typing import Any, Iterator, List, Set
from fluxmonad.plan.node import Node


class UnionNode(Node):
    """Ленивое объединение двух потоков данных (конкатенация)."""

    def __init__(self, parent: Node, other: Node) -> None:
        super().__init__(parent=parent)
        self.other = other

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            yield item
        for item in self.other.evaluate():
            yield item

    def explain_step(self) -> str:
        return "UNION"


class IntersectionNode(Node):
    """Барьерное пересечение двух потоков (оставляет только общие элементы)."""

    def __init__(self, parent: Node, other: Node) -> None:
        super().__init__(parent=parent)
        self.other = other

    @property
    def is_barrier(self) -> bool:
        return True

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        other_items: List[Any] = list(self.other.evaluate())
        try:
            other_set: Set[Any] = set(other_items)
            for item in self.parent.evaluate():
                if item in other_set:
                    yield item
        except TypeError:
            # Fallback для нехешируемых элементов
            for item in self.parent.evaluate():
                if item in other_items:
                    yield item

    def explain_step(self) -> str:
        return "INTERSECTION (barrier=True)"


class DifferenceNode(Node):
    """Барьерная разность потоков (исключает элементы, присутствующие в other)."""

    def __init__(self, parent: Node, other: Node) -> None:
        super().__init__(parent=parent)
        self.other = other

    @property
    def is_barrier(self) -> bool:
        return True

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        other_items: List[Any] = list(self.other.evaluate())
        try:
            other_set: Set[Any] = set(other_items)
            for item in self.parent.evaluate():
                if item not in other_set:
                    yield item
        except TypeError:
            for item in self.parent.evaluate():
                if item not in other_items:
                    yield item

    def explain_step(self) -> str:
        return "DIFFERENCE (barrier=True)"