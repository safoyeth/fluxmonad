from __future__ import annotations

import collections
import functools
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, TypeVar, Union

from fluxmonad.accessors import get_value
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import build_expression
from fluxmonad.diagnostics.explainer import format_explain
from fluxmonad.plan.barriers import DistinctNode, Group, GroupByNode, SortNode
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

    # --- Устранение дубликатов ---

    def distinct(
        self,
        key_selector: Optional[Union[str, Callable[[T], Any]]] = None,
    ) -> Flux[T]:
        """Устраняет повторяющиеся элементы по значению или ключу."""
        return Flux[T](DistinctNode(self._node, key_selector))

    # --- Агрегационные терминальные операции ---

    def sum(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> Union[int, float]:
        """Суммирует элементы или значения полей."""
        total: Union[int, float] = 0
        for item in self:
            val = get_value(item, selector) if isinstance(selector, str) else (selector(item) if callable(selector) else item)
            if val is not None:
                total += val
        return total

    def average(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        """Вычисляет среднее арифметическое элементов потока."""
        total: Union[int, float] = 0
        count = 0
        for item in self:
            val = get_value(item, selector) if isinstance(selector, str) else (selector(item) if callable(selector) else item)
            if val is not None:
                total += val
                count += 1
        if count == 0:
            raise ValueError("Невозможно вычислить average для пустого потока")
        return total / count

    def min(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> T:
        """Находит минимальный элемент."""
        if selector is None:
            return min(self)
        if callable(selector):
            return min(self, key=selector)
        return min(self, key=lambda x: get_value(x, selector))

    def max(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> T:
        """Находит максимальный элемент."""
        if selector is None:
            return max(self)
        if callable(selector):
            return max(self, key=selector)
        return max(self, key=lambda x: get_value(x, selector))

    def materialize(self) -> Flux[T]:
        """
        Материализует текущий пайплайн и возвращает новый Flux,
        основанный на сохранённом неизменяемом кортеже элементов.
        Позволяет безопасно многократно итерироваться по одноразовым генераторам.
        """
        cached_data = tuple(self)
        return Flux[T](cached_data)

    # --- Фабричные методы создания (Data Ingestion) ---

    @classmethod
    def from_json(
        cls,
        path_or_str: Union[str, Any],
        lines: bool = False,
        encoding: str = "utf-8",
    ) -> Flux[Any]:
        """Создает Flux из JSON-файла, строки или JSON Lines."""
        from fluxmonad.sources.loaders import read_json_source
        return cls(read_json_source(path_or_str, lines=lines, encoding=encoding))

    @classmethod
    def from_csv(
        cls,
        filepath: Union[str, Any],
        encoding: str = "utf-8",
        delimiter: str = ",",
    ) -> Flux[Dict[str, Any]]:
        """Лениво читает CSV файл построчно в виде словарей."""
        from fluxmonad.sources.loaders import read_csv_source
        return cls(read_csv_source(filepath, encoding=encoding, delimiter=delimiter))

    @classmethod
    def from_yaml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        """Создает Flux из YAML-файла или строки."""
        from fluxmonad.sources.loaders import read_yaml_source
        return cls(read_yaml_source(path_or_str, encoding=encoding))

    @classmethod
    def from_toml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        """Создает Flux из TOML документа (списка секций или словаря)."""
        from fluxmonad.sources.loaders import read_toml_source
        data = read_toml_source(path_or_str, encoding=encoding)
        # Если TOML содержит корневой список или словарь
        if isinstance(data, list):
            return cls(data)
        return cls([data])

    @classmethod
    def from_pandas(cls, df: Any) -> Flux[Dict[str, Any]]:
        """Преобразует pandas.DataFrame в поток Flux словарей."""
        from fluxmonad.sources.loaders import read_pandas_source
        return cls(read_pandas_source(df))

    @classmethod
    def from_excel(
        cls,
        filepath: Union[str, Any],
        sheet_name: Union[str, int] = 0,
    ) -> Flux[Dict[str, Any]]:
        """Читает лист Excel (.xlsx) построчно в виде словарей."""
        from fluxmonad.sources.loaders import read_excel_source
        return cls(read_excel_source(filepath, sheet_name=sheet_name))

    @classmethod
    def from_file(cls, filepath: Union[str, Any]) -> Flux[Any]:
        """Умная фабрика: определяет формат по расширению файла."""
        p = Path(filepath)
        ext = p.suffix.lower()
        if ext == ".csv":
            return cls.from_csv(p)
        elif ext in (".json", ".jsonl"):
            return cls.from_json(p, lines=(ext == ".jsonl"))
        elif ext in (".yaml", ".yml"):
            return cls.from_yaml(p)
        elif ext == ".toml":
            return cls.from_toml(p)
        elif ext in (".xlsx", ".xlsm"):
            return cls.from_excel(p)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {ext}")