import inspect
from typing import Any, AsyncIterable, Iterable, Iterator
from fluxmonad.plan.node import Node


class SourceNode(Node):
    """Начальный узел потока данных."""

    def __init__(self, source: Any) -> None:
        super().__init__(parent=None)
        self.source = source

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        if inspect.isasyncgen(self.source) or hasattr(self.source, "__aiter__"):
            raise RuntimeError(
                "Асинхронный источник нельзя выполнить через синхронный iter(). "
                "Используйте 'async for item in flux' или 'await flux.collect_async()'."
            )
        if hasattr(self.source, "__iter__"):
            return iter(self.source)
        return iter([self.source])

    async def evaluate_async(self):
        if hasattr(self.source, "__aiter__"):
            async for item in self.source:
                yield item
        else:
            for item in self.evaluate():
                yield item

    def explain_step(self) -> str:
        name = getattr(self.source, "__class__", type(self.source)).__name__
        return f"SOURCE: {name}"