from __future__ import annotations

import collections
import functools
from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, TypeVar, Union

from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import build_expression
from fluxmonad.diagnostics.explainer import format_explain
from fluxmonad.plan.barriers import Group, GroupByNode, SortNode
from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import (
    BindNode,
    ExcludeNode,
    FilterNode,
    MapNode,
    SelectNode,
    SkipNode,
    TakeNode,
)

T = TypeVar("T")
R = TypeVar("R")


class Flux(Generic[T]):
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
        expr = build_expression(predicate, **kwargs)
        return Flux[T](FilterNode(self._node, expr))

    def filterby(
        self,
        predicate: Union[None, Callable[[T], bool], Expression] = None,
        **kwargs: Any,
    ) -> Flux[T]:
        return self.when(predicate, **kwargs)

    # --- DSL Проекции ---

    def select(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
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
        flattened_fields: List[str] = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                flattened_fields.extend(field)
            elif isinstance(field, str):
                flattened_fields.append(field)
            else:
                raise TypeError(f"Поле должно быть строкой или последовательностью строк: {field}")
        return Flux[Dict[str, Any]](ExcludeNode(self._node, flattened_fields))

    # --- DSL Сортировки ---

    def sortby(
        self,
        *keys: Union[str, Callable[[T], Any]],
        reverse: bool = False,
    ) -> Flux[T]:
        """
        Барьерная сортировка элементов.
        Поддерживает: .sortby('age'), .sortby('-age'), .sortby('dept', '-age'),
        а также callable: .sortby(lambda x: x['age']).
        """
        return Flux[T](SortNode(self._node, keys, reverse=reverse))

    # --- DSL Среза и пагинации ---

    def take(self, count: int) -> Flux[T]:
        return Flux[T](TakeNode(self._node, count))

    def skip(self, count: int) -> Flux[T]:
        return Flux[T](SkipNode(self._node, count))

    def head(self, count: int = 1) -> Flux[T]:
        """Синоним к take(n)."""
        return self.take(count)

    def tail(self, count: int = 1) -> Flux[T]:
        """
        Возвращает последние n элементов в виде нового Flux (барьерная операция).
        """
        if count < 0:
            raise ValueError("Параметр count не может быть отрицательным")
        if count == 0:
            return Flux[T]([])
        # Реализуем через deque без загрузки всего потока при бесконечных генераторах
        buffer = collections.deque(self, maxlen=count)
        return Flux[T](list(buffer))

    # --- Терминальные операции ---

    def collect(self) -> List[T]:
        return list(self)

    def first(self, default: Optional[T] = None) -> Optional[T]:
        for item in self:
            return item
        return default

    def last(self, default: Optional[T] = None) -> Optional[T]:
        """Возвращает последний элемент потока."""
        val = default
        has_items = False
        for item in self:
            val = item
            has_items = True
        return val if has_items else default

    def count(self) -> int:
        cnt = 0
        for _ in self:
            cnt += 1
        return cnt

    def exists(self) -> bool:
        """Проверяет наличие хотя бы одного элемента в потоке."""
        for _ in self:
            return True
        return False

    def any(self, predicate: Optional[Callable[[T], bool]] = None) -> bool:
        """True, если хотя бы один элемент удовлетворяет предикату (или поток не пуст)."""
        if predicate is None:
            return self.exists()
        for item in self:
            if predicate(item):
                return True
        return False

    def all(self, predicate: Callable[[T], bool]) -> bool:
        """True, если все элементы удовлетворяют предикату."""
        for item in self:
            if not predicate(item):
                return False
        return True

    def reduce(self, function: Callable[[Any, T], Any], *initial: Any) -> Any:
        """Сворачивает поток с помощью функции function."""
        if initial:
            return functools.reduce(function, self, initial[0])
        return functools.reduce(function, self)

    # --- Диагностика ---

    def explain(self) -> str:
        """Диагностический API: возвращает строковое представление плана вычислений."""
        return format_explain(self._node)

    # --- Группировка ---

    def groupby(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        """
        Барьерная группировка элементов.
        Возвращает Flux[Group], элементы которого содержат .key и .flux (подпоток элементов).
        """
        return Flux[Group[T]](GroupByNode(self._node, key_selector))