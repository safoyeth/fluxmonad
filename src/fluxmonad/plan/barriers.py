import random

from typing import (
    Any, 
    Callable,
    Dict, 
    Iterator, 
    List, 
    Optional, 
    Sequence, 
    Tuple, 
    Union, 
    DefaultDict, 
    Generic, 
    TypeVar, 
    TYPE_CHECKING)
from fluxmonad.accessors import MISSING, get_value
from fluxmonad.plan.node import Node
import collections
if TYPE_CHECKING:
    from fluxmonad.core.flux import Flux

T = TypeVar("T")

class _ComparableWrapper:
    """Wrapper for safe value comparison with support for descending sort direction."""

    __slots__ = ("value", "descending")

    def __init__(self, value: Any, descending: bool = False) -> None:
        self.value = value
        self.descending = descending

    def __lt__(self, other: "_ComparableWrapper") -> bool:
        # If values are equal, neither is less than the other
        if self.value == other.value:
            return False

        # Handle missing and None values
        if self.value is MISSING or self.value is None:
            return not self.descending
        if other.value is MISSING or other.value is None:
            return self.descending

        try:
            less = self.value < other.value
        except TypeError:
            less = str(self.value) < str(other.value)

        # Invert logic if descending is specified
        return not less if self.descending else less

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, _ComparableWrapper):
            return False
        return bool(self.value == other.value)


class SortNode(Node):
    """
    Barrier node for sorting the stream.
    Fully materializes the input stream before ordering.
    """

    def __init__(
        self,
        parent: Node,
        keys: Sequence[Union[str, Callable[[Any], Any]]],
        reverse: bool = False,
    ) -> None:
        super().__init__(parent=parent)
        self.keys = list(keys)
        self.default_reverse = reverse

    @property
    def is_barrier(self) -> bool:
        return True

    def _extract_sort_tuple(self, item: Any) -> Tuple[Any, ...]:
        result = []
        for key in self.keys:
            if callable(key):
                val = key(item)
                result.append(_ComparableWrapper(val, descending=False))
            elif isinstance(key, str):
                is_desc = key.startswith("-")
                path = key[1:] if is_desc else key
                val = get_value(item, path, default=MISSING)
                result.append(_ComparableWrapper(val, descending=is_desc))
            else:
                raise TypeError(f"Sort key must be a string or callable, got {type(key)}")
        return tuple(result)

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        materialized: List[Any] = list(self.parent.evaluate())

        if not self.keys:
            materialized.sort(reverse=self.default_reverse)
        else:
            materialized.sort(
                key=self._extract_sort_tuple,
                reverse=self.default_reverse,
            )

        return iter(materialized)

    def explain_step(self) -> str:
        keys_str = ", ".join(
            getattr(k, "__name__", str(k)) for k in self.keys
        ) or "natural"
        return f"SORT: {keys_str} (barrier=True)"


class Group(Generic[T]):
    """Container for a distinct data group with access to the key and group elements via Flux."""

    __slots__ = ("key", "values")

    def __init__(self, key: Any, values: List[T]) -> None:
        self.key = key
        self.values = values

    @property
    def flux(self) -> "Flux[T]":
        from fluxmonad.core.flux import Flux
        return Flux[T](self.values)

    def __iter__(self) -> Iterator[T]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __repr__(self) -> str:
        return f"Group(key={repr(self.key)}, count={len(self.values)})"

    def aggregate(self, **aggregations: Union[str, Callable[["Flux[T]"], Any]]) -> Dict[str, Any]:
        """
        Computes a set of aggregate metrics over the group's elements.
        Example: group.aggregate(total_salary="sum:salary", avg_age="avg:age", count="count")
        """
        result: Dict[str, Any] = {"key": self.key}
        sub_flux = self.flux

        for target_name, agg_spec in aggregations.items():
            if callable(agg_spec):
                result[target_name] = agg_spec(sub_flux)
            elif isinstance(agg_spec, str):
                tokens = agg_spec.split(":")
                op = tokens[0].lower()
                field = tokens[1] if len(tokens) > 1 else None

                if op == "count":
                    result[target_name] = sub_flux.count()
                elif op == "sum":
                    result[target_name] = sub_flux.sum(field)
                elif op in ("avg", "average"):
                    result[target_name] = sub_flux.average(field)
                elif op == "min":
                    result[target_name] = sub_flux.min(field)
                elif op == "max":
                    result[target_name] = sub_flux.max(field)
                else:
                    raise ValueError(f"Unknown aggregation operation: {op}")
            else:
                raise TypeError(f"Aggregation specification must be a string or callable: {agg_spec}")

        return result

class GroupByNode(Node):
    """
    Barrier node grouping elements by a key selector.
    Emits Group(key, values) objects.
    """

    def __init__(self, parent: Node, key_selector: Union[str, Callable[[Any], Any]]) -> None:
        super().__init__(parent=parent)
        self.key_selector = key_selector

    @property
    def is_barrier(self) -> bool:
        return True

    def _extract_key(self, item: Any) -> Any:
        if callable(self.key_selector):
            return self.key_selector(item)
        if isinstance(self.key_selector, str):
            return get_value(item, self.key_selector, default=None)
        raise TypeError(f"Key selector must be a string or callable: {type(self.key_selector)}")

    def evaluate(self) -> Iterator[Group[Any]]:
        assert self.parent is not None
        groups: DefaultDict[Any, List[Any]] = collections.defaultdict(list)

        # Barrier: materialize incoming stream into groups preserving appearance order
        for item in self.parent.evaluate():
            k = self._extract_key(item)
            groups[k].append(item)

        for key, items in groups.items():
            yield Group(key=key, values=items)

    def explain_step(self) -> str:
        name = getattr(self.key_selector, "__name__", str(self.key_selector))
        return f"GROUPBY: {name} (barrier=True)"

class DistinctNode(Node):
    """
    Barrier node for deduplicating stream elements.
    Supports key selectors: .distinct('id') or .distinct(lambda x: x.email).
    """

    def __init__(
        self,
        parent: Node,
        key_selector: Optional[Union[str, Callable[[Any], Any]]] = None,
    ) -> None:
        super().__init__(parent=parent)
        self.key_selector = key_selector

    @property
    def is_barrier(self) -> bool:
        return True

    def _get_key(self, item: Any) -> Any:
        if self.key_selector is None:
            return item
        if callable(self.key_selector):
            return self.key_selector(item)
        if isinstance(self.key_selector, str):
            return get_value(item, self.key_selector, default=None)
        raise TypeError(f"Key selector must be a string or callable: {type(self.key_selector)}")

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        seen_keys = set()
        seen_unhashable: List[Any] = []

        for item in self.parent.evaluate():
            key = self._get_key(item)
            try:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                yield item
            except TypeError:
                # Fallback for unhashable objects (dicts, lists)
                if key in seen_unhashable:
                    continue
                seen_unhashable.append(key)
                yield item

    def explain_step(self) -> str:
        key_name = getattr(self.key_selector, "__name__", str(self.key_selector)) if self.key_selector else "identity"
        return f"DISTINCT: {key_name} (barrier=True)"

class ReverseNode(Node):
    """
    Barrier node that reverses the order of stream elements.
    Fully materializes the input stream before reversing.
    """

    def __init__(self, parent: Node) -> None:
        super().__init__(parent=parent)

    @property
    def is_barrier(self) -> bool:
        return True

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        materialized = list(self.parent.evaluate())
        materialized.reverse()
        return iter(materialized)

    def explain_step(self) -> str:
        return "REVERSE (barrier=True)"
    
class SampleNode(Node):
    """
    Reservoir sampling of n random elements from a stream.
    Requires O(n) memory regardless of total stream size.
    """

    def __init__(self, parent: Node, n: int, seed: Optional[int] = None) -> None:
        super().__init__(parent=parent)
        if n <= 0:
            raise ValueError("Parameter n must be greater than 0")
        self.n = n
        self.seed = seed

    @property
    def is_barrier(self) -> bool:
        return True

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        rng = random.Random(self.seed)
        reservoir: List[Any] = []

        for idx, item in enumerate(self.parent.evaluate()):
            if idx < self.n:
                reservoir.append(item)
            else:
                j = rng.randint(0, idx)
                if j < self.n:
                    reservoir[j] = item

        return iter(reservoir)

    def explain_step(self) -> str:
        return f"SAMPLE: {self.n} items (barrier=True)"