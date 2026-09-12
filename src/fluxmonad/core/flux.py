from __future__ import annotations

import collections
import functools
import statistics
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar, Union, Type, cast

from fluxmonad.accessors import get_value
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import build_expression
from fluxmonad.diagnostics.explainer import format_explain
from fluxmonad.plan.barriers import DistinctNode, Group, GroupByNode, SortNode, ReverseNode, SampleNode
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
    WindowNode,
    FlattenNode,
    FillNullNode,
    BranchNode,
    CatchNode,
    CompactNode
)
from fluxmonad.plan.analytics import CumulativeSumNode, EnumerateNode, LagLeadNode
from fluxmonad.core.types import alias_for
from fluxmonad.sources.writers import (
    write_csv,
    write_excel,
    write_json,
    write_toml,
    write_yaml,
)
from fluxmonad.diagnostics.profiler import ProfileResult, profile_pipeline
from fluxmonad.plan.concurrency import ParallelMapNode

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
        Lazy iteration through pipeline results.
        The execution plan graph is automatically optimized prior to execution.
        """
        optimized_node = PlanOptimizer.optimize(self._node)
        return iter(optimized_node.evaluate())

    # --- Functional API ---

    def map(self, func: Callable[[T], R]) -> Flux[R]:
        return Flux[R](MapNode(self._node, func))

    def filter(self, predicate: Callable[[T], bool]) -> Flux[T]:
        return Flux[T](FilterNode(self._node, predicate))

    def bind(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return Flux[R](BindNode(self._node, func))

    def __rshift__(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    # --- Filtering DSL ---

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

    # --- Projection DSL ---

    def select(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        flattened_fields: List[str] = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                flattened_fields.extend(field)
            elif isinstance(field, str):
                flattened_fields.append(field)
            else:
                raise TypeError(f"Field must be a string or sequence of strings: {field}")
        return Flux[Dict[str, Any]](SelectNode(self._node, flattened_fields))

    def exclude(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        flattened_fields: List[str] = []
        for field in fields:
            if isinstance(field, (list, tuple)):
                flattened_fields.extend(field)
            elif isinstance(field, str):
                flattened_fields.append(field)
            else:
                raise TypeError(f"Field must be a string or sequence of strings: {field}")
        return Flux[Dict[str, Any]](ExcludeNode(self._node, flattened_fields))

    # --- Sorting DSL ---

    def sortby(
        self,
        *keys: Union[str, Callable[[T], Any]],
        reverse: bool = False,
    ) -> Flux[T]:
        """
        Barrier sorting of stream elements.
        Supports: .sortby('age'), .sortby('-age'), .sortby('dept', '-age'),
        as well as callables: .sortby(lambda x: x['age']).
        """
        return Flux[T](SortNode(self._node, keys, reverse=reverse))

    # --- Slicing & Pagination DSL ---

    def take(self, count: int) -> Flux[T]:
        return Flux[T](TakeNode(self._node, count))

    def skip(self, count: int) -> Flux[T]:
        return Flux[T](SkipNode(self._node, count))

    def head(self, count: int = 1) -> Flux[T]:
        """Synonym for take(n)."""
        return self.take(count)

    def tail(self, count: int = 1) -> Flux[T]:
        """
        Returns the last n elements as a new Flux (barrier operation).
        """
        if count < 0:
            raise ValueError("Parameter count cannot be negative")
        if count == 0:
            return Flux[T]([])
        # Use bounded deque to avoid loading unbounded generators into memory
        buffer = collections.deque(self, maxlen=count)
        return Flux[T](list(buffer))

    # --- Terminal Operations ---
    
    def collect(self) -> List[T]:
        return list(self)

    def first(self, default: Optional[T] = None) -> Optional[T]:
        for item in self:
            return item
        return default

    def last(self, default: Optional[T] = None) -> Optional[T]:
        """Returns the last element of the stream."""
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
        """Checks if the stream contains at least one element."""
        for _ in self:
            return True
        return False

    def any(self, predicate: Optional[Callable[[T], bool]] = None) -> bool:
        """Returns True if any element matches the predicate (or if stream is non-empty when predicate is None)."""
        if predicate is None:
            return self.exists()
        for item in self:
            if predicate(item):
                return True
        return False

    def all(self, predicate: Callable[[T], bool]) -> bool:
        """Returns True if all elements satisfy the predicate."""
        for item in self:
            if not predicate(item):
                return False
        return True

    def reduce(self, function: Callable[[Any, T], Any], *initial: Any) -> Any:
        """Folds the stream using an accumulator function."""
        if initial:
            return functools.reduce(function, self, initial[0])
        return functools.reduce(function, self)

    # --- Diagnostics ---

    def explain(self, optimized: bool = False) -> str:
        """
        Diagnostic API: returns string representation of the execution plan.
        When optimized=True, returns the graph after optimizer transformations.
        """
        target_node = PlanOptimizer.optimize(self._node) if optimized else self._node
        return format_explain(target_node)

    # --- Grouping ---

    def groupby(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        """
        Barrier grouping of elements by key.
        Returns Flux[Group], where each Group contains .key and .flux (sub-stream).
        """
        return Flux(GroupByNode(self._node, key_selector))

    # --- Deduplication ---

    def distinct(
        self,
        key_selector: Optional[Union[str, Callable[[T], Any]]] = None,
    ) -> Flux[T]:
        """Deduplicates elements by value or by key selector."""
        return Flux[T](DistinctNode(self._node, key_selector))

    # --- Aggregations & Metrics ---

    def sum(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> Union[int, float]:
        """Sums stream elements or extracted field values."""
        if selector is None:
            import builtins
            return builtins.sum(cast(Iterable[Union[int, float]], self))

        total: Union[int, float] = 0
        getter: Callable[[Any], Any] = (lambda x: get_value(x, selector)) if isinstance(selector, str) else selector
        for item in self:
            val = getter(item)
            if val is not None:
                total += val
        return total

    def average(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        """Computes arithmetic mean of stream elements or extracted field values."""
        total: Union[int, float] = 0
        count = 0
        if selector is None:
            for item in self:
                if item is not None:
                    total += item  # type: ignore[operator]
                    count += 1
        else:
            getter: Callable[[Any], Any] = (lambda x: get_value(x, selector)) if isinstance(selector, str) else selector
            for item in self:
                val = getter(item)
                if val is not None:
                    total += val
                    count += 1
        if count == 0:
            raise ValueError("Cannot calculate average for an empty stream")
        return total / count

    def min(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> T:
        """Finds minimum element in the stream."""
        if selector is None:
            return min(self, key=lambda x: cast(Any, x))
        if callable(selector):
            return min(self, key=selector)
        return min(self, key=lambda x: get_value(x, selector))

    def max(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> T:
        """Finds maximum element in the stream."""
        if selector is None:
            return max(self, key=lambda x: cast(Any, x))
        if callable(selector):
            return max(self, key=selector)
        return max(self, key=lambda x: get_value(x, selector))

    def materialize(self) -> Flux[T]:
        """
        Materializes the current pipeline and returns a new Flux backed by
        an immutable cached tuple. Enables safe multiple iterations over single-use generators.
        """
        cached_data = tuple(self)
        return Flux[T](cached_data)

    # --- Field Enrichment (ExtendNode) ---

    def extend(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        """
        Adds a computed field to stream elements.
        rule can be a callable, list of path components for concatenation, or a literal constant.
        """
        return Flux[Dict[str, Any]](ExtendNode(self._node, field_name, rule))

    # --- Relational Joins ---

    def join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
        how: str = "inner",
    ) -> Flux[Dict[str, Any]]:
        """
        Relational join with another Flux on specified keys.
        how: 'inner', 'left', 'right', or 'full'.
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
        """Alias for inner join."""
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
        """Alias for left join."""
        return self.join(other, left_on=left_on, right_on=right_on, how="left")

    def leftJoin(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        return self.left_join(other, left_on, right_on)

    # --- Extended Join Methods ---

    def right_join(
        self,
        other: Flux[Any],
        left_on: Union[str, Callable[[T], Any]],
        right_on: Union[str, Callable[[Any], Any]],
    ) -> Flux[Dict[str, Any]]:
        """Right outer join."""
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
        """Full outer join."""
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
        """Cartesian product of two streams (cross join)."""
        return Flux[Dict[str, Any]](CrossJoinNode(self._node, other._node))

    @alias_for(cross_join)
    def crossJoin(self, other: Flux[Any]) -> Flux[Dict[str, Any]]:
        return self.cross_join(other)

    # --- Plan Optimization ---

    def optimize(self) -> Flux[T]:
        """Optimizes current execution graph and returns an optimized Flux."""
        optimized_node = PlanOptimizer.optimize(self._node)
        return Flux[T](optimized_node)

    # --- Set Operations ---

    def union(self, other: Flux[T]) -> Flux[T]:
        """Concatenates current stream with another stream."""
        return Flux[T](UnionNode(self._node, other._node))

    def intersection(self, other: Flux[T]) -> Flux[T]:
        """Returns intersection of elements between two streams."""
        return Flux[T](IntersectionNode(self._node, other._node))

    def difference(self, other: Flux[T]) -> Flux[T]:
        """Excludes elements present in another stream from the current stream."""
        return Flux[T](DifferenceNode(self._node, other._node))

    # --- Field Renaming ---

    def rename(self, **mapping: str) -> Flux[Dict[str, Any]]:
        """
        Renames fields in dictionaries or objects.
        Example: .rename(old_name='new_name', user_id='id')
        """
        return Flux[Dict[str, Any]](RenameNode(self._node, mapping))

    # --- Ingestion Factory Methods ---

    @classmethod
    def from_json(
        cls,
        path_or_str: Union[str, Any],
        lines: bool = False,
        encoding: str = "utf-8",
    ) -> Flux[Any]:
        """Creates a Flux stream from a JSON file, raw JSON string, or JSON Lines."""
        from fluxmonad.sources.loaders import read_json_source
        return Flux[Any](read_json_source(path_or_str, lines=lines, encoding=encoding))

    @classmethod
    def from_csv(
        cls,
        filepath: Union[str, Any],
        encoding: str = "utf-8",
        delimiter: str = ",",
    ) -> Flux[Dict[str, Any]]:
        """Lazily reads a CSV file row-by-row as dictionaries."""
        from fluxmonad.sources.loaders import read_csv_source
        return Flux[Dict[str, Any]](read_csv_source(filepath, encoding=encoding, delimiter=delimiter))

    @classmethod
    def from_yaml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        """Creates a Flux stream from a YAML file or raw string."""
        from fluxmonad.sources.loaders import read_yaml_source
        return Flux[Any](read_yaml_source(path_or_str, encoding=encoding))

    @classmethod
    def from_toml(cls, path_or_str: Union[str, Any], encoding: str = "utf-8") -> Flux[Any]:
        """Creates a Flux stream from a TOML document (section list or dictionary)."""
        from fluxmonad.sources.loaders import read_toml_source
        data = read_toml_source(path_or_str, encoding=encoding)
        # If TOML root contains a list or dictionary
        if isinstance(data, list):
            return Flux[Any](data)
        return Flux[Any]([data])

    @classmethod
    def from_pandas(cls, df: Any) -> Flux[Dict[str, Any]]:
        """Converts a pandas.DataFrame into a streaming Flux of dictionaries."""
        from fluxmonad.sources.loaders import read_pandas_source
        return Flux[Dict[str, Any]](read_pandas_source(df))

    @classmethod
    def from_excel(
        cls,
        filepath: Union[str, Any],
        sheet_name: Union[str, int] = 0,
    ) -> Flux[Dict[str, Any]]:
        """Reads an Excel worksheet (.xlsx) row-by-row as dictionaries."""
        from fluxmonad.sources.loaders import read_excel_source
        return Flux[Dict[str, Any]](read_excel_source(filepath, sheet_name=sheet_name))

    @classmethod
    def from_file(cls, filepath: Union[str, Any]) -> Flux[Any]:
        """Smart factory: detects file format by extension and opens appropriate loader."""
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
            raise ValueError(f"Unsupported file format: {ext}")

    # --- Aliases for when / filterby / where ---

    @alias_for(when)
    def where(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    @alias_for(when)
    def filter_by(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    @alias_for(when)
    def filterBy(self, predicate: Union[None, Callable[[T], bool], Expression] = None, **kwargs: Any) -> Flux[T]:
        return self.when(predicate, **kwargs)

    # --- Aliases for select / exclude ---

    @alias_for(select)
    def project(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        return self.select(*fields)

    @alias_for(exclude)
    def drop(self, *fields: Union[str, Sequence[str]]) -> Flux[Dict[str, Any]]:
        return self.exclude(*fields)

    # --- Aliases for sortby ---

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

    # --- Aliases for extend ---

    @alias_for(extend)
    def with_field(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        return self.extend(field_name, rule)

    @alias_for(extend)
    def withField(self, field_name: str, rule: Any) -> Flux[Dict[str, Any]]:
        return self.extend(field_name, rule)

    # --- Aliases for groupby ---

    @alias_for(groupby)
    def group_by(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        return self.groupby(key_selector)

    @alias_for(groupby)
    def groupBy(self, key_selector: Union[str, Callable[[T], Any]]) -> Flux[Group[T]]:
        return self.groupby(key_selector)

    # --- Aliases for distinct ---

    @alias_for(distinct)
    def unique(self, key_selector: Optional[Union[str, Callable[[T], Any]]] = None) -> Flux[T]:
        return self.distinct(key_selector)

    # --- Aliases for slicing: take / skip ---

    @alias_for(take)
    def limit(self, count: int) -> Flux[T]:
        return self.take(count)

    @alias_for(skip)
    def offset(self, count: int) -> Flux[T]:
        return self.skip(count)

    # --- Aliases for flat_map / bind ---

    @alias_for(bind)
    def flat_map(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    @alias_for(bind)
    def flatMap(self, func: Callable[[T], Iterable[R]]) -> Flux[R]:
        return self.bind(func)

    # --- Aliases for terminal operations ---

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

    # --- Stream Inversion ---

    def reverse(self) -> Flux[T]:
        """Reverses stream element order (barrier operation)."""
        return Flux[T](ReverseNode(self._node))

    # --- Inspection & Logging ---

    def tap(self, action: Callable[[T], None]) -> Flux[T]:
        """
        Executes a side-effect action for each element without mutating stream data.
        Ideal for debugging, telemetry, and pipeline step logging.
        """
        return Flux[T](TapNode(self._node, action))

    @alias_for(tap)
    def peek(self, action: Callable[[T], None]) -> Flux[T]:
        return self.tap(action)

    # --- Stream Pairing ---

    def zip(self, other: Flux[R]) -> Flux[Tuple[T, R]]:
        """Lazily pairs elements of the current Flux with elements of another Flux into tuples."""
        return Flux(ZipNode(self._node, other._node))

    # --- Stream Partitioning ---

    def partition(
        self,
        predicate: Union[None, Callable[[T], bool], Expression] = None,
        **kwargs: Any,
    ) -> Tuple[Flux[T], Flux[T]]:
        """
        Splits the stream into two Flux instances: (matching_flux, not_matching_flux).
        """
        expr = build_expression(predicate, **kwargs)
        # Materialize source so both resulting Flux branches can be iterated independently
        mat = self.materialize()
        matching = mat.when(expr)
        not_matching = mat.when(~expr)
        return matching, not_matching

    # --- Batching & Sliding Windows ---

    def chunk(self, size: int) -> Flux[List[T]]:
        """Splits the stream into non-overlapping batches of size 'size'."""
        return Flux(ChunkNode(self._node, size))

    @alias_for(chunk)
    def batch(self, size: int) -> Flux[List[T]]:
        return self.chunk(size)

    def window(self, size: int, step: int = 1) -> Flux[List[T]]:
        """Generates a sliding window of size 'size' advancing by 'step'."""
        return Flux(WindowNode(self._node, size, step))

    # --- Type Casting ---

    def cast(self, target_type: Callable[[Any], R]) -> Flux[R]:
        """Casts each element to the specified type constructor (e.g., dataclass, Pydantic model, int)."""
        return self.map(target_type)

    # --- Terminal Egress ---

    def to_json(
        self,
        filepath: Union[str, Any],
        lines: bool = False,
        indent: int = 2,
        encoding: str = "utf-8",
    ) -> None:
        """Saves stream elements to a JSON or JSON Lines file."""
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
        """Saves stream elements to a CSV file."""
        write_csv(self, filepath, delimiter=delimiter, encoding=encoding)

    @alias_for(to_csv)
    def toCsv(self, filepath: Union[str, Any], delimiter: str = ",") -> None:
        self.to_csv(filepath, delimiter=delimiter)

    # --- YAML Export ---

    def to_yaml(self, filepath: Union[str, Any], encoding: str = "utf-8") -> None:
        """Saves stream elements to a YAML file."""
        write_yaml(self, filepath, encoding=encoding)

    @alias_for(to_yaml)
    def toYaml(self, filepath: Union[str, Any], encoding: str = "utf-8") -> None:
        self.to_yaml(filepath, encoding=encoding)

    # --- TOML Export ---

    def to_toml(
        self,
        filepath: Union[str, Any],
        root_key: str = "items",
        encoding: str = "utf-8",
    ) -> None:
        """Saves stream elements to a TOML file."""
        write_toml(self, filepath, root_key=root_key, encoding=encoding)

    @alias_for(to_toml)
    def toToml(
        self,
        filepath: Union[str, Any],
        root_key: str = "items",
        encoding: str = "utf-8",
    ) -> None:
        self.to_toml(filepath, root_key=root_key, encoding=encoding)

    # --- Excel Export ---

    def to_excel(
        self,
        filepath: Union[str, Any],
        sheet_name: str = "Sheet1",
    ) -> None:
        """Saves stream elements to an Excel spreadsheet (.xlsx)."""
        write_excel(self, filepath, sheet_name=sheet_name)

    @alias_for(to_excel)
    def toExcel(
        self,
        filepath: Union[str, Any],
        sheet_name: str = "Sheet1",
    ) -> None:
        self.to_excel(filepath, sheet_name=sheet_name)

    # --- Smart File Export ---

    def to_file(self, filepath: Union[str, Any], **kwargs: Any) -> None:
        """Automatically detects destination format by file extension and executes export."""
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
            raise ValueError(f"Unsupported format for export: {ext}")

    @alias_for(to_file)
    def toFile(self, filepath: Union[str, Any], **kwargs: Any) -> None:
        self.to_file(filepath, **kwargs)

    # --- Sequence Analytics ---

    def enumerate(self, start: int = 0, field: Optional[str] = None) -> Flux[Any]:
        """
        Enumerates stream records.
        If field is specified, sets the index under that field in each dictionary/object.
        If field=None, produces a stream of (index, item) tuples.
        """
        return Flux[Any](EnumerateNode(self._node, start=start, field=field))

    def cumulative_sum(self, field: str, target_field: Optional[str] = None) -> Flux[Dict[str, Any]]:
        """Calculates running cumulative sum for the specified numeric field."""
        return Flux[Dict[str, Any]](CumulativeSumNode(self._node, field, target_field))

    @alias_for(cumulative_sum)
    def cumulativeSum(self, field: str, target_field: Optional[str] = None) -> Flux[Dict[str, Any]]:
        return self.cumulative_sum(field, target_field)

    @alias_for(cumulative_sum)
    def running_sum(self, field: str, target_field: Optional[str] = None) -> Flux[Dict[str, Any]]:
        return self.cumulative_sum(field, target_field)

    def lag(
        self,
        field: str,
        offset: int = 1,
        target_field: Optional[str] = None,
        default: Any = None,
    ) -> Flux[Dict[str, Any]]:
        """Appends the value of a field from an earlier record (offset positions back) to current record."""
        return Flux[Dict[str, Any]](
            LagLeadNode(self._node, field, offset=offset, target_field=target_field, default=default, is_lead=False)
        )

    def lead(
        self,
        field: str,
        offset: int = 1,
        target_field: Optional[str] = None,
        default: Any = None,
    ) -> Flux[Dict[str, Any]]:
        """Appends the value of a field from a future record (offset positions ahead) to current record."""
        return Flux[Dict[str, Any]](
            LagLeadNode(self._node, field, offset=offset, target_field=target_field, default=default, is_lead=True)
        )

    # --- Statistical Metrics ---

    def median(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        """Computes stream median."""
        vals: List[float] = [
            float(get_value(item, selector) if isinstance(selector, str) else (selector(item) if callable(selector) else cast(Any, item)))
            for item in self
        ]
        if not vals:
            raise ValueError("Cannot calculate median of an empty stream")
        return float(statistics.median(vals))

    def mode(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> Any:
        """Computes stream mode (most frequent element)."""
        vals = [
            get_value(item, selector) if isinstance(selector, str) else (selector(item) if callable(selector) else item)
            for item in self
        ]
        if not vals:
            raise ValueError("Cannot calculate mode of an empty stream")
        return statistics.mode(vals)

    def std_dev(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        """Computes sample standard deviation."""
        vals: List[float] = [
            float(get_value(item, selector) if isinstance(selector, str) else (selector(item) if callable(selector) else cast(Any, item)))
            for item in self
        ]
        if len(vals) < 2:
            raise ValueError("Standard deviation requires at least two data points")
        return float(statistics.stdev(vals))

    @alias_for(std_dev)
    def stdDev(self, selector: Optional[Union[str, Callable[[T], Any]]] = None) -> float:
        return self.std_dev(selector)

    # --- Structural Flattening ---

    def flatten(self, field: Optional[str] = None) -> Flux[Any]:
        """Unrolls nested lists into the stream root or under the specified field."""
        from fluxmonad.plan.transforms import FlattenNode
        return Flux[Any](FlattenNode(self._node, field))

    # --- Null & Missing Value Handling ---

    def fill_null(self, **defaults: Any) -> Flux[T]:
        """Replaces None or missing values with specified default values."""
        from fluxmonad.plan.transforms import FillNullNode
        return Flux[T](FillNullNode(self._node, defaults))

    @alias_for(fill_null)
    def fillNull(self, **defaults: Any) -> Flux[T]:
        return self.fill_null(**defaults)

    @alias_for(fill_null)
    def fillna(self, **defaults: Any) -> Flux[T]:
        return self.fill_null(**defaults)

    # --- Conditional Branching ---

    def branch(
        self,
        predicate: Callable[[T], bool],
        if_true: Callable[[T], Any],
        if_false: Optional[Callable[[T], Any]] = None,
    ) -> Flux[Any]:
        """Conditional transformation of elements based on a predicate."""
        from fluxmonad.plan.transforms import BranchNode
        return Flux[Any](BranchNode(self._node, predicate, if_true, if_false))

    # --- Sampling ---

    def sample(self, n: int, seed: Optional[int] = None) -> Flux[T]:
        """Reservoir sampling of n random elements from the stream."""
        from fluxmonad.plan.barriers import SampleNode
        return Flux[T](SampleNode(self._node, n, seed=seed))

    # --- Resilience & Error Handling ---

    def catch(
        self,
        handler: Optional[Callable[[Exception, Any], Any]] = None,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> Flux[T]:
        """
        Intercepts exceptions in the stream.
        If handler returns a value, that value is emitted into the stream.
        If handler=None, the failing element is silently dropped.
        """
        return Flux[T](CatchNode(self._node, handler=handler, exceptions=exceptions))

    @alias_for(catch)
    def on_error(
        self,
        handler: Optional[Callable[[Exception, Any], Any]] = None,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> Flux[T]:
        return self.catch(handler=handler, exceptions=exceptions)

    def compact(self) -> Flux[T]:
        """Removes all None elements from the stream."""
        return Flux[T](CompactNode(self._node))

    # --- Async Support ---

    async def __aiter__(self) -> AsyncIterator[T]:
        """Asynchronous iterator for consuming pipeline via async for."""
        for item in self:
            yield item

    async def collect_async(self) -> List[T]:
        """Asynchronously collects stream results into a list."""
        res: List[T] = []
        async for item in self:
            res.append(item)
        return res

    @alias_for(collect_async)
    async def toListAsync(self) -> List[T]:
        return await self.collect_async()

    # --- Concurrency & Parallelism ---

    def parallel_map(
        self,
        func: Callable[[T], R],
        workers: Optional[int] = None,
        chunksize: int = 1,
        backend: str = "thread",
    ) -> Flux[R]:
        """
        Parallel function evaluation over stream elements.
        backend: 'thread' (recommended for I/O bound work) or 'process' (for CPU bound work).
        """
        return Flux[R](
            ParallelMapNode(
                parent=self._node,
                func=func,
                workers=workers,
                chunksize=chunksize,
                backend=backend,
            )
        )

    @alias_for(parallel_map)
    def parallelMap(
        self,
        func: Callable[[T], R],
        workers: Optional[int] = None,
        chunksize: int = 1,
        backend: str = "thread",
    ) -> Flux[R]:
        return self.parallel_map(func, workers=workers, chunksize=chunksize, backend=backend)

    @alias_for(parallel_map)
    def pmap(
        self,
        func: Callable[[T], R],
        workers: Optional[int] = None,
        chunksize: int = 1,
        backend: str = "thread",
    ) -> Flux[R]:
        return self.parallel_map(func, workers=workers, chunksize=chunksize, backend=backend)

    # --- Profiling & Telemetry ---

    def profile(self) -> ProfileResult:
        """
        Executes pipeline while measuring time elapsed and item throughput at each step.
        Returns ProfileResult containing step metrics and final materialized items.
        """
        return profile_pipeline(self._node)