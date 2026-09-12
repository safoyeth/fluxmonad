from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Callable, Iterator, Optional
from fluxmonad.plan.node import Node


class ParallelMapNode(Node):
    """
    Параллельное применение функции к элементам потока.
    backend: 'thread' (для сетевых/дисковых IO операций) или 'process' (для CPU-задач).
    """

    def __init__(
        self,
        parent: Node,
        func: Callable[[Any], Any],
        workers: Optional[int] = None,
        chunksize: int = 1,
        backend: str = "thread",
    ) -> None:
        super().__init__(parent=parent)
        self.func = func
        self.workers = workers
        self.chunksize = chunksize
        self.backend = backend.lower()

        if self.backend not in ("thread", "process"):
            raise ValueError(f"Поддерживаются только бэкенды 'thread' и 'process', получено: {backend}")

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        executor_cls = ThreadPoolExecutor if self.backend == "thread" else ProcessPoolExecutor

        with executor_cls(max_workers=self.workers) as executor:
            stream = self.parent.evaluate()
            yield from executor.map(self.func, stream, chunksize=self.chunksize)

    def explain_step(self) -> str:
        name = getattr(self.func, "__name__", str(self.func))
        return f"PARALLEL_MAP ({self.backend}): {name} (workers={self.workers})"