from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional


class Node(ABC):
    """Base node of the execution plan graph."""

    def __init__(self, parent: Optional["Node"] = None) -> None:
        self.parent = parent

    @property
    @abstractmethod
    def is_barrier(self) -> bool:
        """Indicates whether this node requires full materialization of the preceding stream."""
        pass

    @abstractmethod
    def evaluate(self) -> Iterator[Any]:
        """Initiates lazy stream evaluation for this node."""
        pass

    @abstractmethod
    def explain_step(self) -> str:
        """Returns a string description of the operation for explain()."""
        pass