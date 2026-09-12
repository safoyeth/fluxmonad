# FluxMonad Architecture & Internal Mechanics

FluxMonad is a high-performance, lazy stream processing library designed for Python 3.10+. It combines the formal guarantees of functional monads, the ergonomics of declarative query builders (Django/LINQ style), and the performance of an execution graph rule-based optimizer (RBO).

---

## 1. Core Principles

```
  Data Ingestion (Iterable / CSV / JSON / YAML / TOML / Excel)
                             │
                             ▼
               Pipeline Graph Construction (AST)
            [ SourceNode → TransformNodes → Terminal ]
                             │
                             ▼
                Rule-Based Optimizer (RBO)
            [ Predicate Pushdown, Node Fusion ]
                             │
                             ▼
                 Lazy Iterator Evaluation
         [ O(1) Memory Footprint, Streaming Yield ]
```

1. **Strict Laziness & Bounded Memory**: Computations do not execute upon method call. Operations build a directed acyclic chain of `Node` definitions. Data rows are pulled through generator evaluation one-by-one, guaranteeing bounded memory usage ($O(1)$ memory consumption for purely streaming pipelines).
2. **Monadic Pipeline Laws**: `Flux` complies with Monad laws (Left Identity, Right Identity, Associativity), enabling composable transformations via `bind` and the `>>` operator.
3. **Execution Plan Separation**: Pipeline construction builds an Abstract Syntax Tree (AST) of `Node` instances. Upon terminal evaluation (`__iter__`, `collect`, `first`, `sum`, etc.), the graph is passed to `PlanOptimizer.optimize()` prior to execution.
4. **Transparent Barrier Mechanics**: Operations requiring full materialization (such as `SortNode`, `GroupByNode`, `ReverseNode`) declare `is_barrier = True`. The query optimizer respects barrier boundaries to prevent invalid reordering.

---

## 2. Monad Laws Compliance

In category theory and functional programming, a Monad $(M, \text{unit}, \text{bind})$ must satisfy three foundational laws:

### 2.1 Left Identity
Passing a value $a$ to unit and then binding $f$ is identical to calling $f(a)$:
$$\text{unit}(a) \gg= f \equiv f(a)$$

In FluxMonad:
```python
a = 5
f = lambda x: Flux([x, x * 2])

left = (Flux([a]) >> f).collect()   # [5, 10]
right = f(a).collect()              # [5, 10]
assert left == right
```

### 2.2 Right Identity
Binding `Flux.unit` (or constructor) to a monadic instance returns the instance itself:
$$m \gg= \text{unit} \equiv m$$

In FluxMonad:
```python
m = Flux([1, 2, 3])
unit = lambda x: Flux([x])

assert (m >> unit).collect() == [1, 2, 3]
```

### 2.3 Associativity
Chaining bindings does not depend on grouping:
$$(m \gg= f) \gg= g \equiv m \gg= (\lambda x. f(x) \gg= g)$$

In FluxMonad:
```python
m = Flux([1, 2, 3])
f = lambda x: Flux([x, x + 10])
g = lambda y: Flux([y, y * 100])

left = ((m >> f) >> g).collect()
right = (m >> (lambda x: f(x) >> g)).collect()
assert left == right
```

---

## 3. Node Hierarchy

All transformations extend `fluxmonad.plan.node.Node`:

```
Node (abstract)
 ├── SourceNode
 ├── Transform Nodes (is_barrier = False)
 │    ├── MapNode
 │    ├── FilterNode
 │    ├── SelectNode / ExcludeNode
 │    ├── TakeNode / SkipNode
 │    ├── ExtendNode / RenameNode
 │    ├── ZipNode
 │    ├── TapNode
 │    ├── ChunkNode / WindowNode
 │    ├── FlattenNode / FillNullNode
 │    ├── BranchNode / CatchNode / CompactNode
 │    └── ParallelMapNode
 ├── Analytic Nodes (is_barrier = False, bounded state)
 │    ├── EnumerateNode
 │    ├── CumulativeSumNode
 │    └── LagLeadNode (bounded deque of size offset)
 └── Barrier Nodes (is_barrier = True)
      ├── SortNode
      ├── GroupByNode
      ├── DistinctNode
      ├── ReverseNode
      ├── SampleNode (Reservoir sampling)
      ├── JoinNode / CrossJoinNode
      └── IntersectionNode / DifferenceNode
```

### 3.1 Streaming Nodes (`is_barrier = False`)
Streaming nodes implement `evaluate() -> Iterator[Any]` via generators or `itertools`. They process each element in $O(1)$ auxiliary memory and support early termination (e.g. `take(n)` terminates immediately after receiving $n$ items).

### 3.2 Barrier Nodes (`is_barrier = True`)
Barrier nodes require prior elements to be fully accumulated before emitting results:
- **`SortNode`**: Materializes the upstream stream into a list, performs a Timsort in Python C-internals with custom ASC/DESC comparators, and returns an iterator over the sorted list.
- **`GroupByNode`**: Reads the upstream stream into a `defaultdict(list)`, grouping elements while maintaining key appearance order. Emits `Group(key, values)` instances with isolated sub-fluxes.
- **`SampleNode`**: Implements **Algorithm R (Reservoir Sampling)**, retaining exactly $n$ items with uniform probability in $O(n)$ space regardless of whether the source stream contains $10^6$ or $10^9$ rows.

---

## 4. AST Expression Engine

Instead of opaque Python lambdas that cannot be inspected, FluxMonad provides a composable AST expression engine (`Field`, `Q`, `Expression`):

```python
from fluxmonad import Field, Q

# Operator overloading AST:
expr1 = (Field("age") >= 18) & (Field("status") == "active")

# Django-style Q-expressions:
expr2 = Q(age__gte=18, status="active") | Q(role="admin")
```

Each `Expression` exposes:
- `evaluate(item) -> bool`: Executes evaluation against a dict, object, or mapping using cached path resolvers.
- `referenced_fields -> set[str]`: Inspects which fields are required by the expression. This metadata is the backbone of the **Predicate Pushdown** optimizer.
- `explain() -> str`: Provides human-readable representation for pipeline debugging.

---

## 5. Universal Property Access & Resolvers

FluxMonad traverses heterogeneous Python structures with uniform syntax:
- Dictionary key: `get_value(data, "user.name")`
- Attribute access: `get_value(obj, "user.address.city")`
- Sequence indexing: `get_value(data, "items.0.price")`
- Deep Search (`..` syntax): `get_value(data, "meta..token")` recursively searches mapping and attribute trees using depth-first search (DFS) with LRU caching.
