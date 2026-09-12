from fluxmonad import Field, Flux


def test_inner_join():
    users = Flux([
        {"id": 1, "name": "Alice", "dept_id": 10},
        {"id": 2, "name": "Bob", "dept_id": 20},
        {"id": 3, "name": "Charlie", "dept_id": 30},
    ])

    departments = Flux([
        {"d_id": 10, "dept_name": "Engineering"},
        {"d_id": 20, "dept_name": "HR"},
    ])

    joined = (
        users.inner_join(departments, left_on="dept_id", right_on="d_id")
        .select("name", "dept_name")
        .collect()
    )

    assert joined == [
        {"name": "Alice", "dept_name": "Engineering"},
        {"name": "Bob", "dept_name": "HR"},
    ]


def test_left_join():
    users = Flux([
        {"id": 1, "name": "Alice", "dept_id": 10},
        {"id": 3, "name": "Charlie", "dept_id": 99},
    ])

    departments = Flux([
        {"d_id": 10, "dept_name": "Engineering"},
    ])

    joined = (
        users.left_join(departments, left_on="dept_id", right_on="d_id")
        .select("name", "dept_name")
        .collect()
    )

    assert joined == [
        {"name": "Alice", "dept_name": "Engineering"},
        {"name": "Charlie", "dept_name": None},
    ]


def test_plan_optimizer_take_collapse():
    # take(100).take(10) должно сжаться в take(10)
    pipeline = Flux(range(1000)).take(100).take(10).optimize()
    plan_str = pipeline.explain()

    assert "TAKE: 10" in plan_str
    assert "TAKE: 100" not in plan_str
    assert pipeline.collect() == list(range(10))


def test_plan_optimizer_filter_merge():
    # Две фильтрации подряд объединяются в одно выражение And
    pipeline = (
        Flux([{"val": 5}, {"val": 15}, {"val": 25}])
        .when(val__gt=10)
        .when(val__lt=20)
        .optimize()
    )

    assert pipeline.collect() == [{"val": 15}]
    explanation = pipeline.explain()
    assert "(val > 10 AND val < 20)" in explanation