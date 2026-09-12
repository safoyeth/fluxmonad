import itertools
import copy
from typing import Any, Callable, Dict, Iterator, Tuple, Deque, List, Sequence, Union, Optional, Type

from fluxmonad.accessors import project_exclude, project_select
from fluxmonad.accessors.resolver import MISSING, get_value
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import LambdaExpression

from fluxmonad.plan.node import Node


class MapNode(Node):
    """Streaming element transformation."""

    def __init__(self, parent: Node, func: Callable[[Any], Any]) -> None:
        super().__init__(parent=parent)
        self.func = func

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return map(self.func, self.parent.evaluate())

    def explain_step(self) -> str:
        return f"MAP: {getattr(self.func, '__name__', str(self.func))}"


class FilterNode(Node):
    """Streaming element filtering based on an expression or predicate."""

    def __init__(self, parent: Node, predicate_or_expr: Union[Callable[[Any], bool], Expression]) -> None:
        super().__init__(parent=parent)
        if isinstance(predicate_or_expr, Expression):
            self.expr = predicate_or_expr
        else:
            self.expr = LambdaExpression(predicate_or_expr)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return filter(self.expr.evaluate, self.parent.evaluate())

    def explain_step(self) -> str:
        return f"FILTER: {self.expr.explain()}"


class SelectNode(Node):
    """Streaming projection: retains only the specified fields."""

    def __init__(self, parent: Node, fields: Sequence[str]) -> None:
        super().__init__(parent=parent)
        self.fields = list(fields)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            yield project_select(item, self.fields)

    def explain_step(self) -> str:
        return f"SELECT: {', '.join(self.fields)}"


class ExcludeNode(Node):
    """Streaming projection: excludes the specified fields."""

    def __init__(self, parent: Node, fields: Sequence[str]) -> None:
        super().__init__(parent=parent)
        self.fields = list(fields)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            yield project_exclude(item, self.fields)

    def explain_step(self) -> str:
        return f"EXCLUDE: {', '.join(self.fields)}"


class TakeNode(Node):
    """Streaming element count limiter with early termination."""

    def __init__(self, parent: Node, count: int) -> None:
        super().__init__(parent=parent)
        if count < 0:
            raise ValueError("Parameter count cannot be negative")
        self.count = count

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return itertools.islice(self.parent.evaluate(), self.count)

    def explain_step(self) -> str:
        return f"TAKE: {self.count}"

class BindNode(Node):
    """
    Monadic bind node (flat_map).
    Applies func to each element and flattens the resulting
    collection (one level of nesting) in a streaming fashion.
    """

    def __init__(self, parent: Node, func: Callable[[Any], Any]) -> None:
        super().__init__(parent=parent)
        self.func = func

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            sub_result = self.func(item)
            # Support standard Iterables, Flux instances, and generators
            for sub_item in sub_result:
                yield sub_item

    def explain_step(self) -> str:
        return f"BIND: {getattr(self.func, '__name__', str(self.func))}"

class SkipNode(Node):
    """Streaming skip of the first n elements."""

    def __init__(self, parent: Node, count: int) -> None:
        super().__init__(parent=parent)
        if count < 0:
            raise ValueError("Parameter count cannot be negative")
        self.count = count

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return itertools.islice(self.parent.evaluate(), self.count, None)

    def explain_step(self) -> str:
        return f"SKIP: {self.count}"

class ExtendNode(Node):
    """
    Streaming enrichment of elements with a new or calculated field.
    Returns a shallow copy of the dictionary or object with the added field.
    """

    def __init__(self, parent: Node, field_name: str, rule: Any) -> None:
        super().__init__(parent=parent)
        self.field_name = field_name
        self.rule = rule

    @property
    def is_barrier(self) -> bool:
        return False

    @property
    def target_field(self) -> str:
        return self.field_name

    def _compute_value(self, item: Any) -> Any:
        if callable(self.rule):
            return self.rule(item)

        if isinstance(self.rule, (list, tuple)):
            parts = []
            for part in self.rule:
                if isinstance(part, str):
                    # If string is not a valid field path (contains spaces, etc.), use as literal
                    if " " in part or not part.strip():
                        parts.append(part)
                        continue

                    try:
                        val = get_value(item, part, default=MISSING)
                        parts.append(str(val) if val is not MISSING else part)
                    except ValueError:
                        # If path syntax is invalid, fall back to string literal
                        parts.append(part)
                else:
                    parts.append(str(part))
            return "".join(parts)

        return self.rule

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        rule = self.rule
        field_name = self.field_name
        compute = rule if callable(rule) else self._compute_value
        for item in self.parent.evaluate():
            computed = compute(item)
            if isinstance(item, dict):
                new_item = item.copy()
                new_item[field_name] = computed
                yield new_item
            else:
                # For custom objects, enrich a shallow copy
                import copy
                new_obj = copy.copy(item)
                setattr(new_obj, field_name, computed)
                yield new_obj

    def explain_step(self) -> str:
        return f"EXTEND: {self.field_name}"

class RenameNode(Node):
    """Streaming renaming of fields in dictionaries or objects."""

    def __init__(self, parent: Node, mapping: Dict[str, str]) -> None:
        super().__init__(parent=parent)
        self.mapping = mapping

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if isinstance(item, dict):
                new_item = dict(item)
                for old_key, new_key in self.mapping.items():
                    if old_key in new_item:
                        new_item[new_key] = new_item.pop(old_key)
                yield new_item
            else:
                import copy
                new_obj = copy.copy(item)
                for old_key, new_key in self.mapping.items():
                    if hasattr(new_obj, old_key):
                        val = getattr(new_obj, old_key)
                        delattr(new_obj, old_key)
                        setattr(new_obj, new_key, val)
                yield new_obj

    def explain_step(self) -> str:
        pairs = ", ".join(f"{k}->{v}" for k, v in self.mapping.items())
        return f"RENAME: {pairs}"

class ZipNode(Node):
    """Streaming pairing of elements from the current stream with another stream."""

    def __init__(self, parent: Node, other: Node) -> None:
        super().__init__(parent=parent)
        self.other = other

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Tuple[Any, Any]]:
        assert self.parent is not None
        return zip(self.parent.evaluate(), self.other.evaluate())

    def explain_step(self) -> str:
        return "ZIP"


class TapNode(Node):
    """
    Streaming execution of a side effect (logging, debugging, metric collection)
    for each element without mutating the stream items.
    """

    def __init__(self, parent: Node, action: Callable[[Any], None]) -> None:
        super().__init__(parent=parent)
        self.action = action

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            self.action(item)
            yield item

    def explain_step(self) -> str:
        name = getattr(self.action, "__name__", str(self.action))
        return f"TAP: {name}"

class ChunkNode(Node):
    """Streaming slicing of stream elements into fixed-size batches."""

    def __init__(self, parent: Node, size: int) -> None:
        super().__init__(parent=parent)
        if size <= 0:
            raise ValueError("Chunk size must be strictly greater than 0")
        self.size = size

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[List[Any]]:
        assert self.parent is not None
        batch: List[Any] = []
        for item in self.parent.evaluate():
            batch.append(item)
            if len(batch) == self.size:
                yield batch
                batch = []
        if batch:
            yield batch

    def explain_step(self) -> str:
        return f"CHUNK: {self.size}"


class WindowNode(Node):
    """Streaming sliding window over elements."""

    def __init__(self, parent: Node, size: int, step: int = 1) -> None:
        super().__init__(parent=parent)
        if size <= 0 or step <= 0:
            raise ValueError("Window size and step must be greater than 0")
        self.size = size
        self.step = step

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[List[Any]]:
        assert self.parent is not None
        buffer: List[Any] = []
        for item in self.parent.evaluate():
            buffer.append(item)
            if len(buffer) == self.size:
                yield list(buffer)
                buffer = buffer[self.step:]

    def explain_step(self) -> str:
        return f"WINDOW: size={self.size}, step={self.step}"

class FlattenNode(Node):
    """Unrolls nested collections (or lists within a designated field)."""

    def __init__(self, parent: Node, field: Optional[str] = None) -> None:
        super().__init__(parent=parent)
        self.field = field

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if self.field is None:
                if isinstance(item, (list, tuple, set)):
                    yield from item
                else:
                    yield item
            else:
                raw_val = get_value(item, self.field, default=[])
                if isinstance(raw_val, (list, tuple, set)):
                    for sub_val in raw_val:
                        if isinstance(item, dict):
                            new_item = dict(item)
                            new_item[self.field] = sub_val
                            yield new_item
                        else:
                            new_obj = copy.copy(item)
                            setattr(new_obj, self.field, sub_val)
                            yield new_obj
                else:
                    yield item

    def explain_step(self) -> str:
        return f"FLATTEN: {self.field or 'root'}"


class FillNullNode(Node):
    """Replaces None or missing values with defaults."""

    def __init__(self, parent: Node, defaults: Dict[str, Any]) -> None:
        super().__init__(parent=parent)
        self.defaults = defaults

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if isinstance(item, dict):
                new_item = dict(item)
                for field, default_val in self.defaults.items():
                    if new_item.get(field) is None:
                        new_item[field] = default_val
                yield new_item
            else:
                new_obj = copy.copy(item)
                for field, default_val in self.defaults.items():
                    if getattr(new_obj, field, None) is None:
                        setattr(new_obj, field, default_val)
                yield new_obj

    def explain_step(self) -> str:
        keys = ", ".join(f"{k}={v}" for k, v in self.defaults.items())
        return f"FILL_NULL: {keys}"


class BranchNode(Node):
    """
    Applies if_true(item) if predicate(item) evaluates to True,
    otherwise applies if_false(item) (if provided).
    """

    def __init__(
        self,
        parent: Node,
        predicate: Callable[[Any], bool],
        if_true: Callable[[Any], Any],
        if_false: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        super().__init__(parent=parent)
        self.predicate = predicate
        self.if_true = if_true
        self.if_false = if_false

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if self.predicate(item):
                yield self.if_true(item)
            elif self.if_false is not None:
                yield self.if_false(item)
            else:
                yield item

    def explain_step(self) -> str:
        return "BRANCH (conditional transform)"

class CatchNode(Node):
    """
    Intercepts exceptions during element evaluation.
    Enables falling back to alternative values or gracefully skipping failing items.
    """

    def __init__(
        self,
        parent: Node,
        handler: Optional[Callable[[Exception, Any], Any]] = None,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        super().__init__(parent=parent)
        self.handler = handler
        self.exceptions = exceptions

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None

        # If parent is MapNode, apply func with call-level protection
        # to ensure errors do not break the generator
        if isinstance(self.parent, MapNode):
            upstream = self.parent.parent.evaluate() if self.parent.parent else iter([])
            func = self.parent.func
            for raw_item in upstream:
                try:
                    yield func(raw_item)
                except self.exceptions as exc:
                    if self.handler is not None:
                        fallback = self.handler(exc, raw_item)
                        if fallback is not None:
                            yield fallback
            return

        # General case for other node types
        iterator = iter(self.parent.evaluate())
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                break
            except self.exceptions as exc:
                if self.handler is not None:
                    fallback = self.handler(exc, None)
                    if fallback is not None:
                        yield fallback
                continue
            yield item

    def explain_step(self) -> str:
        exc_names = ", ".join(e.__name__ for e in self.exceptions)
        return f"CATCH: ({exc_names})"


class CompactNode(Node):
    """Streaming filter removing None values."""

    def __init__(self, parent: Node) -> None:
        super().__init__(parent=parent)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if item is not None:
                yield item

    def explain_step(self) -> str:
        return "COMPACT"