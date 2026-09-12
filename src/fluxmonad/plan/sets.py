from typing import Any, Iterator, List, Set
from fluxmonad.plan.node import Node


class UnionNode(Node):
    """Lazy union of two data streams (concatenation)."""

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
    """Barrier intersection of two streams (retains only common elements)."""

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
            # Fallback for unhashable elements
            for item in self.parent.evaluate():
                if item in other_items:
                    yield item

    def explain_step(self) -> str:
        return "INTERSECTION (barrier=True)"


class DifferenceNode(Node):
    """Barrier difference of two streams (excludes elements present in other)."""

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