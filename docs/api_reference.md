# FluxMonad API Reference

A comprehensive technical reference for the public classes, methods, and expressions in `fluxmonad`.

---

## 1. Class: `Flux[T]`

Import:
```python
from fluxmonad import Flux
```

### 1.1 Ingestion & Factory Methods
- **`Flux(source)`**: Constructor. Accepts any `Iterable[T]` or execution `Node`.
- **`Flux.from_json(path_or_str, lines=False, encoding="utf-8")`**: Reads JSON or NDJSON/JSON Lines.
- **`Flux.from_csv(filepath, encoding="utf-8", delimiter=",")`**: Streams CSV rows as dictionaries.
- **`Flux.from_yaml(path_or_str, encoding="utf-8")`**: Reads YAML file or raw YAML string.
- **`Flux.from_toml(path_or_str, encoding="utf-8")`**: Reads TOML documents.
- **`Flux.from_excel(filepath, sheet_name=0)`**: Reads `.xlsx` spreadsheets row-by-row via `openpyxl`.
- **`Flux.from_pandas(df)`**: Converts a Pandas DataFrame into a streaming Flux of dictionaries.
- **`Flux.from_file(filepath)`**: Auto-detects format from extension (`.csv`, `.json`, `.jsonl`, `.yaml`, `.toml`, `.xlsx`).

### 1.2 Transformations
- **`.map(func: Callable[[T], R]) -> Flux[R]`**: Transforms each element with `func`.
- **`.filter(predicate: Callable[[T], bool]) -> Flux[T]`**: Filters elements matching `predicate`.
- **`.bind(func: Callable[[T], Iterable[R]]) -> Flux[R]`**: Monadic flatMap ($M \gg= f$).
- **`flux >> func`**: Operator alias for `.bind(func)`.
- **`.extend(field_name: str, rule: Any) -> Flux[Dict[str, Any]]`**: Adds a new computed or static field. `rule` may be a callable `lambda r: ...`, a list of path segments for string interpolation, or a constant. (Alias: `.with_field()`).
- **`.select(*fields: str) -> Flux[Dict[str, Any]]`**: Retains only the specified fields. (Alias: `.project()`).
- **`.exclude(*fields: str) -> Flux[Dict[str, Any]]`**: Drops the specified fields. (Alias: `.drop()`).
- **`.rename(**mapping: str) -> Flux[Dict[str, Any]]`**: Renames keys/attributes (e.g. `old_name="new_name"`).
- **`.cast(target_type: Callable[[Any], R]) -> Flux[R]`**: Casts each element to a type constructor (dataclass, model, int, etc.).
- **`.flatten(field: Optional[str] = None) -> Flux[Any]`**: Flattens nested sequences either in stream root or within a field.
- **`.fill_null(**defaults: Any) -> Flux[T]`**: Replaces `None` or missing field values with defaults. (Aliases: `.fillna()`, `.fillNull()`).
- **`.compact() -> Flux[T]`**: Filters out `None` values.
- **`.branch(predicate, if_true, if_false=None) -> Flux[Any]`**: Conditional row mapping.
- **`.catch(handler=None, exceptions=(Exception,)) -> Flux[T]`**: Intercepts errors during row processing.

### 1.3 Declarative Filtering
- **`.when(predicate=None, **kwargs) -> Flux[T]`**: Filter using `Expression`, `Q`, or Django-style kwargs (`age__gte=18`, `role="admin"`). (Aliases: `.where()`, `.filterby()`, `.filter_by()`).

### 1.4 Slicing & Windowing
- **`.take(count: int) -> Flux[T]`**: Takes the first `count` elements with early termination. (Aliases: `.head()`, `.limit()`).
- **`.skip(count: int) -> Flux[T]`**: Skips the first `count` elements. (Alias: `.offset()`).
- **`.tail(count: int = 1) -> Flux[T]`**: Returns the last `count` elements using a bounded buffer.
- **`.chunk(size: int) -> Flux[List[T]]`**: Batches elements into fixed-size lists. (Alias: `.batch()`).
- **`.window(size: int, step: int = 1) -> Flux[List[T]]`**: Produces a sliding window of elements.

### 1.5 Sorting, Grouping & Barriers
- **`.sortby(*keys, reverse=False) -> Flux[T]`**: Sorts stream elements by fields or callables. Supports prefix `"-"` for descending order (e.g. `"-age"`). (Aliases: `.sort_by()`, `.order_by()`).
- **`.groupby(key_selector) -> Flux[Group[T]]`**: Groups elements into `Group` instances with sub-fluxes. (Alias: `.group_by()`).
- **`.distinct(key_selector=None) -> Flux[T]`**: Deduplicates stream elements. (Alias: `.unique()`).
- **`.reverse() -> Flux[T]`**: Reverses stream order.
- **`.sample(n: int, seed=None) -> Flux[T]`**: Reservoir sampling of `n` items with uniform probability.

### 1.6 Relational Joins & Sets
- **`.join(other, left_on, right_on, how="inner") -> Flux[Dict[str, Any]]`**: Hash join with modes `'inner'`, `'left'`, `'right'`, `'full'`.
- **`.inner_join(other, left_on, right_on)`**: Inner join alias.
- **`.left_join(other, left_on, right_on)`**: Left outer join alias.
- **`.right_join(other, left_on, right_on)`**: Right outer join alias.
- **`.full_join(other, left_on, right_on)`**: Full outer join alias.
- **`.cross_join(other) -> Flux[Dict[str, Any]]`**: Cartesian product of two streams.
- **`.union(other: Flux[T]) -> Flux[T]`**: Lazy stream concatenation.
- **`.intersection(other: Flux[T]) -> Flux[T]`**: Barrier intersection.
- **`.difference(other: Flux[T]) -> Flux[T]`**: Barrier difference.
- **`.zip(other: Flux[R]) -> Flux[Tuple[T, R]]`**: Streams tuples of paired items.
- **`.partition(predicate, **kwargs) -> Tuple[Flux[T], Flux[T]]`**: Splits stream into `(matching_flux, not_matching_flux)`.

### 1.7 Analytical Operations
- **`.enumerate(start=0, field=None) -> Flux[Any]`**: Adds an index column or produces `(index, item)` tuples.
- **`.cumulative_sum(field, target_field=None) -> Flux[Dict[str, Any]]`**: Running cumulative sum. (Aliases: `.running_sum()`, `.cumulativeSum()`).
- **`.lag(field, offset=1, target_field=None, default=None)`**: Looks back `offset` positions.
- **`.lead(field, offset=1, target_field=None, default=None)`**: Looks ahead `offset` positions.

### 1.8 Concurrency & Side Effects
- **`.parallel_map(func, workers=None, chunksize=1, backend="thread") -> Flux[R]`**: Evaluates `func` concurrently using thread or process pools. (Aliases: `.parallelMap()`, `.pmap()`).
- **`.tap(action: Callable[[T], None]) -> Flux[T]`**: Executes a side-effect (logging, metrics) without mutating items. (Alias: `.peek()`).

### 1.9 Materialization & Terminal Operations
- **`.collect() -> List[T]`**: Materializes stream into a Python list. (Aliases: `.to_list()`, `.toList()`).
- **`.first(default=None) -> Optional[T]`**: Returns first element or default.
- **`.last(default=None) -> Optional[T]`**: Returns last element or default.
- **`.count() -> int`**: Counts total items.
- **`.exists() -> bool`**: Returns True if stream contains at least one item.
- **`.any(predicate=None) -> bool`**: Returns True if any item matches predicate.
- **`.all(predicate) -> bool`**: Returns True if all items match predicate.
- **`.reduce(func, *initial) -> Any`**: Folds stream with an accumulator.
- **`.sum(selector=None) -> Union[int, float]`**: Computes sum.
- **`.average(selector=None) -> float`**: Computes average. (Alias: `.avg()`).
- **`.min(selector=None) -> T`**: Finds minimum element.
- **`.max(selector=None) -> T`**: Finds maximum element.
- **`.median(selector=None) -> float`**: Computes median.
- **`.mode(selector=None) -> Any`**: Computes mode.
- **`.std_dev(selector=None) -> float`**: Computes sample standard deviation. (Alias: `.stdDev()`).
- **`.materialize() -> Flux[T]`**: Freezes stream into an immutable tuple for safe repeated iteration.
- **`.to_json(filepath, lines=False, indent=2)`**: Writes stream to JSON / JSON Lines.
- **`.to_csv(filepath, delimiter=",")`**: Writes stream to CSV.
- **`.to_yaml(filepath)`**: Writes stream to YAML.
- **`.to_toml(filepath, root_key="items")`**: Writes stream to TOML.
- **`.to_excel(filepath, sheet_name="Sheet1")`**: Writes stream to Excel.
- **`.to_file(filepath, **kwargs)`**: Writes to file, auto-detecting extension.
- **`async for item in flux`**: Asynchronous iteration protocol.
- **`await flux.collect_async()`**: Asynchronously materializes into a list. (Alias: `.toListAsync()`).

### 1.10 Diagnostics & Telemetry
- **`.explain(optimized=False) -> str`**: Returns ASCII diagram of the execution plan graph.
- **`.profile() -> ProfileResult`**: Measures execution duration and items processed per step.

---

## 2. Class: `Field`

Constructs strongly-typed filter expressions using Python operators:

```python
from fluxmonad import Field

Field("age") >= 18
Field("name") == "Alice"
Field("status") != "archived"
Field("role").is_in(["admin", "manager"])
Field("tags").contains("staff")
```

Supports boolean operators `&` (AND), `|` (OR), and `~` (NOT).

---

## 3. Class: `Q`

Django-style keyword query builder:

```python
from fluxmonad import Q

q = Q(age__gte=18, status="active") | Q(role="superadmin")
Flux(users).when(q)
```

Supported lookups:
- `__exact` or `__eq`: Equal to (`==`)
- `__ne`: Not equal to (`!=`)
- `__gt`: Greater than (`>`)
- `__gte`: Greater than or equal to (`>=`)
- `__lt`: Less than (`<`)
- `__lte`: Less than or equal to (`<=`)
- `__in`: In sequence (`in`)
- `__contains`: Sequence contains item
