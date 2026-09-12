import gc
import sys
import time
import tracemalloc
from itertools import islice
from typing import Any, Callable, Generator, Iterator, Tuple

from fluxmonad import Field, Flux


def generate_records(n: int) -> Generator[dict[str, Any], None, None]:
    """Ленивый генератор миллиона записей без удержания в памяти."""
    for i in range(n):
        yield {
            "id": i,
            "age": i % 100,
            "score": (i * 13) % 1000,
            "status": "active" if i % 2 == 0 else "pending",
        }


def profile(func: Callable[[], Any]) -> Tuple[float, float, Any]:
    """Измеряет время выполнения (сек) и пиковую память (МБ)."""
    gc.collect()
    tracemalloc.start()
    start_time = time.perf_counter()

    result = func()

    elapsed = time.perf_counter() - start_time
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()

    peak_mb = peak_bytes / (1024 * 1024)
    return elapsed, peak_mb, result


def run_benchmarks() -> None:
    n_items = 1_000_000
    print(f"\n🚀 Запуск бенчмарков FluxMonad (объем потока: {n_items:,} записей)\n" + "=" * 65)

    # -------------------------------------------------------------
    # Сценарий 1: Ранняя остановка (Take 10,000 после фильтрации)
    # -------------------------------------------------------------
    print("\n[Сценарий 1] Потоковый ETL + Ранняя отсечка: Filter -> Map -> Take(10_000)")

    def bench_itertools_take() -> list[dict[str, Any]]:
        stream = generate_records(n_items)
        filtered = (r for r in stream if r["age"] >= 18 and r["status"] == "active")
        mapped = ({**r, "normalized_score": r["score"] / 1000.0} for r in filtered)
        return list(islice(mapped, 10_000))

    def bench_flux_take() -> list[dict[str, Any]]:
        return (
            Flux(generate_records(n_items))
            .when(Field("age") >= 18)
            .when(Field("status") == "active")
            .extend("normalized_score", lambda r: r["score"] / 1000.0)
            .take(10_000)
            .to_list()
        )

    t_iter, m_iter, res_iter = profile(bench_itertools_take)
    t_flux, m_flux, res_flux = profile(bench_flux_take)

    assert len(res_iter) == len(res_flux) == 10_000

    print(f"  • itertools : {t_iter:.4f}s | Пиковая память: {m_iter:.2f} MB")
    print(f"  • FluxMonad : {t_flux:.4f}s | Пиковая память: {m_flux:.2f} MB")

    # -------------------------------------------------------------
    # Сценарий 2: Predicate Pushdown (Оптимизация порядка вычислений)
    # -------------------------------------------------------------
    print("\n[Сценарий 2] Тяжёлая проекция -> Фильтрация по базовому полю")
    print("             Тяжелая функция: строковая интерполяция и хэширование")

    def heavy_computation(r: dict[str, Any]) -> str:
        return f"hash_{hash(r['id'])}_{r['score']}"

    # Наивный пайплайн в чистом Python: трансформируем ВСЕ строки, потом фильтруем
    def bench_naive_itertools() -> list[dict[str, Any]]:
        stream = generate_records(100_000)
        # Тяжёлая трансформация вызывается для 100% элементов
        extended = ({**r, "token": heavy_computation(r)} for r in stream)
        # Отсекаем 90% элементов после тяжёлой операции
        filtered = (r for r in extended if r["age"] >= 90)
        return list(filtered)

    # FluxMonad: благодаря Predicate Pushdown фильтр 'age >= 90'
    # перемещается ПЕРЕД extend(), снижая нагрузку на CPU в 10 раз
    def bench_flux_pushdown() -> list[dict[str, Any]]:
        return (
            Flux(generate_records(100_000))
            .extend("token", heavy_computation)
            .when(Field("age") >= 90)  # Будет протолкнут оптимизатором перед extend()
            .to_list()
        )

    t_naive, m_naive, res_n = profile(bench_naive_itertools)
    t_opt, m_opt, res_o = profile(bench_flux_pushdown)

    assert len(res_n) == len(res_o)

    print(f"  • Чистый Python (без оптимизатора) : {t_naive:.4f}s | Память: {m_naive:.2f} MB")
    print(f"  • FluxMonad (c Predicate Pushdown) : {t_opt:.4f}s | Память: {m_opt:.2f} MB")
    speedup = ((t_naive - t_opt) / t_naive) * 100 if t_naive > t_opt else 0.0
    print(f"  ⚡ Ускорение благодаря оптимизатору: {speedup:.1f}%")

    # -------------------------------------------------------------
    # Сценарий 3: Полный обход и редукция 1,000,000 записей
    # -------------------------------------------------------------
    print("\n[Сценарий 3] Редукция полного потока (Sum по 1,000,000 строк)")

    def bench_itertools_sum() -> float:
        stream = generate_records(n_items)
        return sum(r["score"] for r in stream)

    def bench_flux_sum() -> float:
        return (
            Flux(generate_records(n_items))
            .map(lambda r: r["score"])
            .sum()
        )

    t_sum_iter, m_sum_iter, val_iter = profile(bench_itertools_sum)
    t_sum_flux, m_sum_flux, val_flux = profile(bench_flux_sum)

    assert val_iter == val_flux

    print(f"  • sum(generator) : {t_sum_iter:.4f}s | Пиковая память: {m_sum_iter:.2f} MB")
    print(f"  • Flux.sum()     : {t_sum_flux:.4f}s | Пиковая память: {m_sum_flux:.2f} MB")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_benchmarks()