from __future__ import annotations

from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, TypeVar, Union

from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import build_expression
from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import (
    BindNode,
    ExcludeNode,
    FilterNode,
    MapNode,
    SelectNode,
    TakeNode,
)

T = TypeVar("T")
R = TypeVar("R")


class Flux(Generic[T]):
    """Ленивый иммутабельный функциональный контейнер над графом вычислений."""

    __slots__ = ("_node",)

    def __init__(self, source_or_node: Union[Iterable[T], Node]) -> None:
        if isinstance(source_or_node, Node):
            self._node = source_or_node
        else:
            self._node = SourceNode(source_or_node)

    def __iter__(self) -> Iterator[T]:
        return iter(self._node.evaluate())

    # --- Функциональный API ---

    def map(self, func: Callable[[T], R]) -> Flux[R]:
        return Flux[R](MapNode(self._node, func))

    def filter(self, predicate: Callable[[T], bool]) -> Flux[T]:
        return Flux[T](FilterNode(self._node, predicate))

    def bind(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return Flux[R](BindNode(self._node, func))

    def __rshift__(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    # --- DSL Фильтрации ---

    def when(
        self,
        predicate: Union[None, Callable[[T], bool], Expression] = None,
        **kwargs: Any,
    ) -> Flux[T]:
        """
        Основной DSL-фильтр. Принимает предикат, Expression или kwargs.
        Пример: .when(age__gte=18, status="active")
        """
        expr = build_expression(predicate, **kwargs)
        return Flux[T](FilterNode(self._node, expr))

    def filterby(
        self,
        predicate: Union[None, Callable[[T], bool], Expression] = None,
        **kwargs: Any,
    ) -> Flux[T]:
        """Синоним к when()."""
        return self.when(predicate, **kwargs)

    # --- DSL Проекции ---

    def select(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        """
        Проецирует каждый элемент в словарь с заданными полями.
        Принимает аргументы как через запятую, так и списком:
        .select("name", "age") или .select(["name", "age"])
        """
        flattened_fields: List[str] = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                flattened_fields.extend(field)
            elif isinstance(field, str):
                flattened_fields.append(field)
            else:
                raise TypeError(f"Поле должно быть строкой или последовательностью строк: {field}")

        return Flux[Dict[str, Any]](SelectNode(self._node, flattened_fields))

    def exclude(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        """Исключает указанные поля из структуры."""
        flattened_fields: List[str] = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                flattened_fields.extend(field)
            elif isinstance(field, str):
                flattened_fields.append(field)
            else:
                raise TypeError(f"Поле должно быть строкой или последовательностью строк: {field}")

        return Flux[Dict[str, Any]](ExcludeNode(self._node, flattened_fields))

    # --- DSL Среза и пагинации ---

    def take(self, count: int) -> Flux[T]:
        return Flux[T](TakeNode(self._node, count))

    # --- Терминальные операции ---

    def collect(self) -> List[T]:
        return list(self)

    def first(self, default: Optional[T] = None) -> Optional[T]:
        for item in self:
            return item
        return default

    def count(self) -> int:
        cnt = 0
        for _ in self:
            cnt += 1
        return cnt