from __future__ import annotations

import collections
import functools
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar, Union

from fluxmonad.accessors import get_value
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import build_expression
from fluxmonad.diagnostics.explainer import format_explain
from fluxmonad.plan.barriers import DistinctNode, Group, GroupByNode, SortNode, ReverseNode
from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.joins import JoinNode, CrossJoinNode
from fluxmonad.plan.optimizer import PlanOptimizer
from fluxmonad.plan.sets import DifferenceNode, IntersectionNode, UnionNode
from fluxmonad.plan.transforms import (
    BindNode,
    ExcludeNode,
    FilterNode,
    MapNode,
    SelectNode,
    SkipNode,
    TakeNode,
    ExtendNode,
    RenameNode,
    ZipNode,
    TapNode,
    ChunkNode,
    WindowNode
)
from fluxmonad.core.types import alias_for
from fluxmonad.sources.writers import (
    write_csv,
    write_excel,
    write_json,
    write_toml,
    write_yaml,
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
        """
        Ленивая итерация по результатам пайплайна.
        Перед выполнением граф автоматически оптимизируется.
        """
        optimized_node = PlanOptimizer.optimize(self._node)
        return iter(optimized_node.evaluate())

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

    def explain(self, optimized: bool = False) -> str:
        """
        Диагностический API: возвращает строковое представление плана вычислений.
        При optimized=True возвращает граф после применения оптимизатора.
        """
        target_node = PlanOptimizer.optimize(self._node) if optimized else self._node
        return format_explain(target_node)

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

    # --  Добавление полей к элементам потока (ExtendNode)  ---

    def extend(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        """
        Добавляет вычисляемое поле в поток.
        rule может быть callable, списком компонентов для склейки или константой.
        """
        return Flux[Dict[str, Any]](ExtendNode(self._node, field_name, rule))

    # --- Реляционные операции (Joins) ---

    def join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
        how: str = "inner",
    ) -> Flux[Dict[str, Any]]:
        """
        Реляционное объединение с другим Flux по указанным ключам.
        how: 'inner' или 'left'.
        """
        return Flux[Dict[str, Any]](
            JoinNode(
                left_parent=self._node,
                right_parent=other._node,
                left_on=left_on,
                right_on=right_on,
                how=how,
            )
        )

    def inner_join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        """Алиас для внутреннего объединения (inner join)."""
        return self.join(other, left_on=left_on, right_on=right_on, how="inner")

    def innerJoin(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        return self.inner_join(other, left_on, right_on)

    def left_join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        """Алиас для левого объединения (left join)."""
        return self.join(other, left_on=left_on, right_on=right_on, how="left")

    def leftJoin(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        return self.left_join(other, left_on, right_on)

    # --- Новые методы Join ---

    def right_join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        """Правое внешнее объединение (right outer join)."""
        return self.join(other, left_on=left_on, right_on=right_on, how="right")

    @alias_for(right_join)
    def rightJoin(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        return self.right_join(other, left_on, right_on)

    def full_join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        """Полное внешнее объединение (full outer join)."""
        return self.join(other, left_on=left_on, right_on=right_on, how="full")

    @alias_for(full_join)
    def fullJoin(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        return self.full_join(other, left_on, right_on)

    def cross_join(self, other: Flux[Any]) -> Flux[Dict[str, Any]]:
        """Декартово произведение двух потоков (cross join)."""
        return Flux[Dict[str, Any]](CrossJoinNode(self._node, other._node))

    @alias_for(cross_join)
    def crossJoin(self, other: Flux[Any]) -> Flux[Dict[str, Any]]:
        return self.cross_join(other)

    # --- Оптимизация плана ---

    def optimize(self) -> Flux[T]:
        """Оптимизирует текущий граф вычислений и возвращает оптимизированный Flux."""
        optimized_node = PlanOptimizer.optimize(self._node)
        return Flux[T](optimized_node)

    # --- Операции со множествами ---

    def union(self, other: Flux[T]) -> Flux[T]:
        """Объединяет текущий поток с другим потоком."""
        return Flux[T](UnionNode(self._node, other._node))

    def intersection(self, other: Flux[T]) -> Flux[T]:
        """Возвращает пересечение элементов двух потоков."""
        return Flux[T](IntersectionNode(self._node, other._node))

    def difference(self, other: Flux[T]) -> Flux[T]:
        """Исключает из текущего потока элементы другого потока."""
        return Flux[T](DifferenceNode(self._node, other._node))

    # --- Переименование полей ---

    def rename(self, **mapping: str) -> Flux[Dict[str, Any]]:
        """
        Переименовывает поля в потоке.
        Пример: .rename(old_name='new_name', user_id='id')
        """
        return Flux[Dict[str, Any]](RenameNode(self._node, mapping))

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

    # --- Алиасы для when / filterby / where ---

    @alias_for(when)
    def where(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    @alias_for(when)
    def filter_by(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    @alias_for(when)
    def filterBy(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    # --- Алиасы для select / exclude ---

    @alias_for(select)
    def project(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        return self.select(*fields)

    @alias_for(exclude)
    def drop(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        return self.exclude(*fields)

    # --- Алиасы для sortby ---

    @alias_for(sortby)
    def sort_by(self, *keys: Union[str, Callable[[T], Any]], reverse: bool = False) -> Flux[T]:
        return self.sortby(*keys, reverse=reverse)

    @alias_for(sortby)
    def sortBy(self, *keys: Union[str, Callable[[T], Any]], reverse: bool = False) -> Flux[T]:
        return self.sortby(*keys, reverse=reverse)

    @alias_for(sortby)
    def order_by(self, *keys: Union[str, Callable[[T], Any]], reverse: bool = False) -> Flux[T]:
        return self.sortby(*keys, reverse=reverse)

    @alias_for(sortby)
    def orderBy(self, *keys: Union[str, Callable[[T], Any]], reverse: bool = False) -> Flux[T]:
        return self.sortby(*keys, reverse=reverse)

    # --- Алиасы для extend ---

    @alias_for(extend)
    def with_field(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        return self.extend(field_name, rule)

    @alias_for(extend)
    def withField(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        return self.extend(field_name, rule)

    # --- Алиасы для groupby ---

    @alias_for(groupby)
    def group_by(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        return self.groupby(key_selector)

    @alias_for(groupby)
    def groupBy(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        return self.groupby(key_selector)

    # --- Алиасы для distinct ---

    @alias_for(distinct)
    def unique(self, key_selector: Optional[Union[str, Callable[[T], Any]]] = None) -> Flux[T]:
        return self.distinct(key_selector)

    # --- Алиасы для срезов: take / skip ---

    @alias_for(take)
    def limit(self, count: int) -> Flux[T]:
        return self.take(count)

    @alias_for(skip)
    def offset(self, count: int) -> Flux[T]:
        return self.skip(count)

    # --- Алиасы для flat_map / bind ---

    @alias_for(bind)
    def flat_map(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    @alias_for(bind)
    def flatMap(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    # --- Алиасы для терминальных операций ---

    @alias_for(collect)
    def to_list(self) -> List[T]:
        return self.collect()

    @alias_for(collect)
    def toList(self) -> List[T]:
        return self.collect()

    @alias_for(average)
    def avg(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        return self.average(selector)

    @classmethod
    @alias_for(from_json)
    def fromJson(cls, path_or_str: Union[str, Any], lines: bool = False, encoding: str = "utf-8") -> Flux[Any]:
        return cls.from_json(path_or_str, lines=lines, encoding=encoding)

    @classmethod
    @alias_for(from_csv)
    def fromCsv(cls, filepath: Union[str, Any], encoding: str = "utf-8", delimiter: str = ",") -> Flux[Dict[str, Any]]:
        return cls.from_csv(filepath, encoding=encoding, delimiter=delimiter)

    @classmethod
    @alias_for(from_yaml)
    def fromYaml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        return cls.from_yaml(path_or_str, encoding=encoding)

    @classmethod
    @alias_for(from_toml)
    def fromToml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        return cls.from_toml(path_or_str, encoding=encoding)

    @classmethod
    @alias_for(from_pandas)
    def fromPandas(cls, df: Any) -> Flux[Dict[str, Any]]:
        return cls.from_pandas(df)

    @classmethod
    @alias_for(from_excel)
    def fromExcel(cls, filepath: Union[str, Any], sheet_name: Union[str, int] = 0) -> Flux[Dict[str, Any]]:
        return cls.from_excel(filepath, sheet_name=sheet_name)

    @classmethod
    @alias_for(from_file)
    def fromFile(cls, filepath: Union[str, Any]) -> Flux[Any]:
        return cls.from_file(filepath)

    @alias_for(rename)
    def rename_fields(self, **mapping: str) -> Flux[Dict[str, Any]]:
        return self.rename(**mapping)

    @alias_for(rename)
    def renameFields(self, **mapping: str) -> Flux[Dict[str, Any]]:
        return self.rename(**mapping)

    # --- Разворот потока ---

    def reverse(self) -> Flux[T]:
        """Инвертирует порядок элементов потока (барьерная операция)."""
        return Flux[T](ReverseNode(self._node))

    # --- Инспекция / Logging ---

    def tap(self, action: Callable[[T], None]) -> Flux[T]:
        """
        Выполняет действие над каждым элементом потока без изменения данных.
        Идеально подходит для логирования шагов пайплайна.
        """
        return Flux[T](TapNode(self._node, action))

    @alias_for(tap)
    def peek(self, action: Callable[[T], None]) -> Flux[T]:
        return self.tap(action)

    # --- Спаривание потоков ---

    def zip(self, other: Flux[R]) -> Flux[Tuple[T, R]]:
        """Потоково объединяет элементы текущего Flux с элементами другого Flux в кортежи."""
        return Flux[Tuple[T, R]](ZipNode(self._node, other._node))

    # --- Разделение потока ---

    def partition(
        self,
        predicate: Union[None, Callable[[T], bool], Expression] = None,
        **kwargs: Any,
    ) -> Tuple[Flux[T], Flux[T]]:
        """
        Разделяет поток на два Flux: (matching_flux, not_matching_flux).
        """
        expr = build_expression(predicate, **kwargs)
        # Материализуем источник, чтобы оба потока могли независимо итерироваться
        mat = self.materialize()
        matching = mat.when(expr)
        not_matching = mat.when(~expr)
        return matching, not_matching

    # --- Пакетирование и окна ---

    def chunk(self, size: int) -> Flux[List[T]]:
        """Разбивает поток на непересекающиеся списки размера size."""
        return Flux[List[T]](ChunkNode(self._node, size))

    @alias_for(chunk)
    def batch(self, size: int) -> Flux[List[T]]:
        return self.chunk(size)

    def window(self, size: int, step: int = 1) -> Flux[List[T]]:
        """Формирует скользящее окно размера size с шагом step."""
        return Flux[List[T]](WindowNode(self._node, size, step))

    # --- Приведение типов ---

    def cast(self, target_type: Callable[[Any], R]) -> Flux[R]:
        """Приводит каждый элемент к указанному типу (например, dataclass, Pydantic модель, int)."""
        return self.map(target_type)

    # --- Терминальный экспорт (Data Egress) ---

    def to_json(
        self,
        filepath: Union[str, Any],
        lines: bool = False,
        indent: int = 2,
        encoding: str = "utf-8",
    ) -> None:
        """Сохраняет элементы потока в JSON или JSON Lines."""
        write_json(self, filepath, lines=lines, indent=indent, encoding=encoding)

    @alias_for(to_json)
    def toJson(self, filepath: Union[str, Any], lines: bool = False, indent: int = 2) -> None:
        self.to_json(filepath, lines=lines, indent=indent)

    def to_csv(
        self,
        filepath: Union[str, Any],
        delimiter: str = ",",
        encoding: str = "utf-8",
    ) -> None:
        """Сохраняет элементы потока в CSV."""
        write_csv(self, filepath, delimiter=delimiter, encoding=encoding)

    @alias_for(to_csv)
    def toCsv(self, filepath: Union[str, Any], delimiter: str = ",") -> None:
        self.to_csv(filepath, delimiter=delimiter)

    # --- Запись YAML ---

    def to_yaml(self, filepath: Union[str, Any], encoding: str = "utf-8") -> None:
        """Сохраняет элементы потока в YAML-файл."""
        write_yaml(self, filepath, encoding=encoding)

    @alias_for(to_yaml)
    def toYaml(self, filepath: Union[str, Any], encoding: str = "utf-8") -> None:
        self.to_yaml(filepath, encoding=encoding)

    # --- Запись TOML ---

    def to_toml(
        self,
        filepath: Union[str, Any],
        root_key: str = "items",
        encoding: str = "utf-8",
    ) -> None:
        """Сохраняет элементы потока в TOML-файл."""
        write_toml(self, filepath, root_key=root_key, encoding=encoding)

    @alias_for(to_toml)
    def toToml(
        self,
        filepath: Union[str, Any],
        root_key: str = "items",
        encoding: str = "utf-8",
    ) -> None:
        self.to_toml(filepath, root_key=root_key, encoding=encoding)

    # --- Запись Excel ---

    def to_excel(
        self,
        filepath: Union[str, Any],
        sheet_name: str = "Sheet1",
    ) -> None:
        """Сохраняет элементы потока в таблицу Excel (.xlsx)."""
        write_excel(self, filepath, sheet_name=sheet_name)

    @alias_for(to_excel)
    def toExcel(
        self,
        filepath: Union[str, Any],
        sheet_name: str = "Sheet1",
    ) -> None:
        self.to_excel(filepath, sheet_name=sheet_name)

    # --- Умный метод сохранения по расширению ---

    def to_file(self, filepath: Union[str, Any], **kwargs: Any) -> None:
        """Автоматически определяет формат по расширению файла и выполняет экспорт."""
        p = Path(filepath)
        ext = p.suffix.lower()
        if ext == ".csv":
            self.to_csv(p, **kwargs)
        elif ext in (".json", ".jsonl"):
            lines = kwargs.pop("lines", ext == ".jsonl")
            self.to_json(p, lines=lines, **kwargs)
        elif ext in (".yaml", ".yml"):
            self.to_yaml(p, **kwargs)
        elif ext == ".toml":
            self.to_toml(p, **kwargs)
        elif ext in (".xlsx", ".xlsm"):
            self.to_excel(p, **kwargs)
        else:
            raise ValueError(f"Неподдерживаемый формат для сохранения: {ext}")

    @alias_for(to_file)
    def toFile(self, filepath: Union[str, Any], **kwargs: Any) -> None:
        self.to_file(filepath, **kwargs)