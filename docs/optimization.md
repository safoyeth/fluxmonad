# Execution Plan Optimization & Predicate Pushdown

**[English](optimization.md)** | **[Русский](optimization_ru.md)**

FluxMonad features an integrated **Rule-Based Optimizer (RBO)** implemented in `PlanOptimizer`. The optimizer analyzes the pipeline's execution graph and applies algebraic transformations before any data is pulled from the source.

---

## 1. What is Predicate Pushdown?

In naive stream pipelines, expensive data transformations are often executed on rows that are later discarded by subsequent filters:

```
Naive Execution (Without Optimizer):
  Source (1,000,000 items)
      ↓
  Heavy Computation / Extend (Calculated for 1,000,000 items)  ← 100% CPU Cost
      ↓
  Filter ('age >= 90') (Discards 90% of items)
      ↓
  Output (100,000 items)
```

With **Predicate Pushdown**, FluxMonad statically moves `FilterNode` ahead of independent transformations:

```
Optimized Execution (With Predicate Pushdown):
  Source (1,000,000 items)
      ↓
  Filter ('age >= 90') (Filters out 900,000 items FIRST)     ← Cheap check
      ↓
  Heavy Computation / Extend (Calculated for 100,000 items ONLY) ← 90% CPU Savings!
      ↓
  Output (100,000 items)
```

In benchmark Scenario 2, this optimization results in a **54%+ reduction in execution time**.

---

## 2. Dependency Safety Analysis (`_can_swap`)

An optimization is valid if and only if it does not change the semantic output of the program. FluxMonad uses dependency checking before swapping any `FilterNode` with an upstream node:

### 2.1 Swapping past `ExtendNode`
- The optimizer inspects `filter_node.expr.referenced_fields`.
- If the target field produced by `ExtendNode` (e.g. `token`) is in `referenced_fields`, the filter **depends** on the computed field and **cannot be pushed upstream**:
  ```python
  # Filter DEPENDS on 'token': CANNOT swap
  Flux(data).extend("token", heavy_func).when(Field("token").contains("abc"))
  ```
- If the filter checks unrelated fields (e.g. `age >= 18`), the swap is completely safe:
  ```python
  # Filter depends on 'age', not 'token': PUSHED UPSTREAM
  Flux(data).extend("token", heavy_func).when(Field("age") >= 18)
  ```

### 2.2 Swapping past `RenameNode`
- If any old key or new key in the rename mapping intersects with the filter's dependencies, the nodes cannot be swapped without rewriting the predicate. FluxMonad safely preserves the order.

### 2.3 Swapping past `TapNode`
- `TapNode` has zero data-mutating side effects on elements. Filters can always safely move across `TapNode`.

### 2.4 Respecting Barriers
- Filters are never swapped past barrier nodes (`SortNode`, `GroupByNode`, `ReverseNode`) or `SourceNode`.

---

## 3. Node Fusion Rules

Adjacent nodes of the same type are algebraically folded into single composite nodes:

### 3.1 Take Fusion
Multiple consecutive `take` limits are collapsed into the tightest bound:
$$\text{Take}(n_1) \circ \text{Take}(n_2) \implies \text{Take}(\min(n_1, n_2))$$

If any `take(0)` is encountered, the entire pipeline collapses into an empty `SourceNode([])`, avoiding any upstream stream reads.

### 3.2 Skip Fusion
Consecutive skips are summed:
$$\text{Skip}(s_1) \circ \text{Skip}(s_2) \implies \text{Skip}(s_1 + s_2)$$

### 3.3 Filter Fusion
Adjacent filters are combined using logical `And`:
$$\text{Filter}(P_1) \circ \text{Filter}(P_2) \implies \text{Filter}(P_1 \land P_2)$$

This minimizes generator wrapping layers and frame invocation overhead.

---

## 4. Visualizing the Optimizer with `explain()`

You can inspect both the raw and optimized execution graphs using `.explain()`:

```python
from fluxmonad import Flux, Field

pipeline = (
    Flux(range(1000))
    .extend("heavy_token", lambda x: str(x) * 10)
    .when(Field("value") > 500)
    .take(20)
    .take(5)
)

print(pipeline.explain(optimized=False))
# Flux execution plan
# SOURCE: range
#   ↓
# EXTEND: heavy_token
#   ↓
# FILTER: value > 500
#   ↓
# TAKE: 20
#   ↓
# TAKE: 5

print(pipeline.explain(optimized=True))
# Flux execution plan
# SOURCE: range
#   ↓
# FILTER: value > 500      <-- Pushed before EXTEND
#   ↓
# EXTEND: heavy_token
#   ↓
# TAKE: 5                  <-- 20 and 5 collapsed into 5
```
