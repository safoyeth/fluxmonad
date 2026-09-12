# FluxMonad Performance Benchmarks

This document reports performance benchmarks measured on **1,000,000 stream records** comparing FluxMonad against native Python generator pipelines (`itertools`).

Benchmark script: [`benchmarks/benchmarks.py`](file:///home/safoyeth/Документы/fluxmonad/benchmarks/benchmarks.py)  
Telemetry tool: Python `tracemalloc` (peak memory tracking) & `time.perf_counter`.

---

## 1. Summary of Benchmark Results

| Scenario | Pure Python / `itertools` | FluxMonad | Memory Footprint | Relative Performance |
| :--- | :--- | :--- | :--- | :--- |
| **1. Stream ETL + Early Cutoff** <br> `Filter -> Map -> Take(10k)` | 0.1065s | 0.1596s | 2.60 MB vs 2.62 MB | Comparable speed with full monadic encapsulation |
| **2. Heavy Projection + Filter** <br> `Extend -> When(Predicate)` | 0.8852s | **0.4065s** | 2.91 MB vs 2.90 MB | **⚡ 54.1% Faster** (via Predicate Pushdown) |
| **3. Full Stream Reduction** <br> `Sum over 1,000,000 rows` | 2.7208s | 2.8061s | 0.00 MB vs 0.01 MB | Zero memory retention ($O(1)$ peak RAM) |

---

## 2. Detailed Scenario Analysis

### Scenario 1: Streaming ETL with Early Stop (`Take(10,000)`)
- **Objective**: Verify that lazy evaluation does not consume or retain unnecessary records past the cutoff boundary.
- **Workflow**: 1,000,000 records $\to$ Filter by `age >= 18` and `status == "active"` $\to$ Extend with normalized score $\to$ `take(10_000)`.
- **Finding**: Both `itertools` and `FluxMonad` evaluate lazily, stopping immediately after row 10,000. Memory is bounded strictly to the size of the result buffer (~2.6 MB).

### Scenario 2: Heavy Projection with Predicate Pushdown
- **Objective**: Measure CPU optimization when an expensive projection is placed before an independent filter.
- **Operation**:
  ```python
  Flux(stream)
      .extend("token", heavy_hash_computation)
      .when(Field("age") >= 90)  # Drops 90% of rows
      .to_list()
  ```
- **Pure Python**: Naively calculates `heavy_hash_computation` for 100% of rows (100,000 times) before discarding 90% in the filter $\to$ **0.8852s**.
- **FluxMonad**: The rule-based optimizer identifies that the filter depends only on `age`, pushing it ahead of `extend()`. `heavy_hash_computation` is invoked for only 10% of items $\to$ **0.4065s (54.1% CPU reduction)**.

### Scenario 3: 1,000,000 Row Stream Aggregation
- **Objective**: Measure streaming throughput and garbage collection stability during full stream reduction.
- **Finding**: Running `Flux.sum()` across 1,000,000 records completes in 2.80s with virtually zero heap allocation (peak delta ~0.01 MB), demonstrating true constant memory streaming.

---

## 3. Running Benchmarks Locally

Execute the benchmark suite using:

```bash
PYTHONPATH=src python3 benchmarks/benchmarks.py
```
