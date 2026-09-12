from __future__ import annotations

from typing import Any, Callable, Generic, Iterable, Iterator, List, Optional, TypeVar, Union

from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import BindNode, FilterNode, MapNode, TakeNode

T = TypeVar("T")
R = TypeVar("R")


class Flux(Generic[T]):
    """
    Ленивый иммутабельный функциональный контейнер над графом вычислений.
    """

    __slots__ = ("_node",)

    def __init__(self, source_or_node: Union[Iterable[T], Node]) -> None:
        if isinstance(source_or_node, Node):
            self._node = source_or_node
        else:
            self._node = SourceNode(source_or_node)

    # --- Итерация и протоколы ---

    def __iter__(self) -> Iterator[T]:
        """Прямая итерация по результатам пайплайна."""
        return iter(self._node.evaluate())

    # --- Функциональный API ---

    def map(self, func: Callable[[T], R]) -> Flux[R]:
        """Применяет функцию к каждому элементу потока."""
        return Flux[R](MapNode(self._node, func))

    def filter(self, predicate: Callable[[T], bool]) -> Flux[T]:
        """Фильтрует поток по предикату."""
        return Flux[T](FilterNode(self._node, predicate))

    def bind(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        """
        Монадическая операция bind (flat_map).
        Разворачивает возвращаемые последовательности на один уровень.
        """
        return Flux[R](BindNode(self._node, func))

    def __rshift__(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        """Оператор >> как синоним bind."""
        return self.bind(func)

    # --- Базовые DSL-операции среза ---

    def take(self, count: int) -> Flux[T]:
        """Ограничивает выборку первыми `count` элементами с ранней остановкой."""
        return Flux[T](TakeNode(self._node, count))

    # --- Терминальные операции ---

    def collect(self) -> List[T]:
        """Материализует результат в стандартный Python list."""
        return list(self)

    def first(self, default: Optional[T] = None) -> Optional[T]:
        """Возвращает первый элемент потока или default, если поток пуст."""
        for item in self:
            return item
        return default

    def count(self) -> int:
        """Подсчитывает количество элементов в потоке."""
        cnt = 0
        for _ in self:
            cnt += 1
        return cnt