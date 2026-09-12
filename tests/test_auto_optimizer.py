from fluxmonad import Flux


def test_auto_optimizer_on_iteration():
    # Проверяем, что даже без вызова .optimize() цепочка сжимается
    pipeline = Flux(range(1000)).take(100).take(5)

    # При итерации отрабатывает оптимизированный граф
    assert pipeline.collect() == [0, 1, 2, 3, 4]


def test_explain_optimized_flag():
    pipeline = (
        Flux([{"val": 5}, {"val": 15}, {"val": 25}])
        .when(val__gt=10)
        .where(val__lt=20)
    )

    raw_plan = pipeline.explain()
    opt_plan = pipeline.explain(optimized=True)

    # В исходном плане 2 отдельных узла FILTER
    assert raw_plan.count("FILTER:") == 2

    # В оптимизированном плане узлы объединены в один And
    assert opt_plan.count("FILTER:") == 1
    assert "(val > 10 AND val < 20)" in opt_plan