from fluxmonad import Field, Flux


def test_pushdown_through_extend():
    data = [{"id": 1, "age": 25}, {"id": 2, "age": 15}]

    # Фильтр по age не зависит от вычисляемого поля "is_adult"
    pipeline = (
        Flux(data)
        .extend("label", lambda r: f"user_{r['id']}")
        .when(Field("age") >= 18)
    )

    raw_plan = pipeline.explain()
    opt_plan = pipeline.explain(optimized=True)

    # В исходном плане FILTER стоит после EXTEND
    assert raw_plan.index("EXTEND:") < raw_plan.index("FILTER:")

    # В оптимизированном плане FILTER вытолкнут перед EXTEND
    assert opt_plan.index("FILTER:") < opt_plan.index("EXTEND:")

    # Результат выполнения совпадает
    assert pipeline.collect() == [{"id": 1, "age": 25, "label": "user_1"}]


def test_pushdown_through_tap():
    side_effects = []
    data = [10, 20, 30]

    # Фильтр x > 15 должен выполниться до tap, чтобы tap не обрабатывал число 10
    pipeline = (
        Flux(data)
        .tap(lambda x: side_effects.append(x))
        .when(lambda x: x > 15)
        .optimize()
    )

    plan = pipeline.explain()
    # FILTER встал перед TAP
    assert plan.index("FILTER:") < plan.index("TAP:")

    result = pipeline.collect()
    assert result == [20, 30]
    assert side_effects == [20, 30]


def test_no_pushdown_when_field_is_dependent():
    data = [{"first": "A", "last": "B"}]

    # Фильтр проверяет вычисляемое поле 'fullname' — переносить нельзя
    pipeline = (
        Flux(data)
        .extend("fullname", ["first", " ", "last"])
        .when(Field("fullname") == "A B")
    )

    opt_plan = pipeline.explain(optimized=True)
    # Порядок должен сохраниться: EXTEND -> FILTER
    assert opt_plan.index("EXTEND:") < opt_plan.index("FILTER:")
    assert len(pipeline.collect()) == 1