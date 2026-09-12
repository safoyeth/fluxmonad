from typing import Any, Iterable, Iterator

from fluxmonad.plan.node import Node


class SourceNode(Node):
    """Корневой узел, представляющий исходную коллекцию данных."""

    def __init__(self, source: Iterable[Any]) -> None:
        super().__init__(parent=None)
        self._source = source

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        return iter(self._source)

    def explain_step(self) -> str:
        source_type = type(self._source).__name__
        return f"SOURCE: {source_type}"