from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional


class Node(ABC):
    """Базовый узел графа плана исполнения."""

    def __init__(self, parent: Optional["Node"] = None) -> None:
        self.parent = parent

    @property
    @abstractmethod
    def is_barrier(self) -> bool:
        """Указывает, требует ли узел полной материализации предшествующего потока."""
        pass

    @abstractmethod
    def evaluate(self) -> Iterator[Any]:
        """Запускает ленивую итерацию по узлу."""
        pass

    @abstractmethod
    def explain_step(self) -> str:
        """Возвращает строковое описание операции для explain()."""
        pass