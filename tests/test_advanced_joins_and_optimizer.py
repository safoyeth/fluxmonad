from fluxmonad import Flux


def test_right_join():
    users = Flux([
        {"user_id": 1, "name": "Alice", "dept_id": 10},
    ])
    departments = Flux([
        {"id": 10, "dept_name": "Engineering"},
        {"id": 20, "dept_name": "Sales"},
    ])

    result = (
        users.right_join(departments, left_on="dept_id", right_on="id")
        .select("name", "dept_name")
        .collect()
    )

    assert result == [
        {"name": "Alice", "dept_name": "Engineering"},
        {"name": None, "dept_name": "Sales"},
    ]


def test_full_join():
    left = Flux([
        {"id": 1, "val_l": "A"},
        {"id": 2, "val_l": "B"},
    ])
    right = Flux([
        {"id": 2, "val_r": "X"},
        {"id": 3, "val_r": "Y"},
    ])

    result = left.full_join(right, left_on="id", right_on="id").collect()

    assert result == [
        {"id": 1, "val_l": "A"},
        {"id": 2, "val_l": "B", "val_r": "X"},
        {"id": 3, "val_r": "Y"},
    ]


def test_cross_join():
    colors = Flux([{"color": "red"}, {"color": "blue"}])
    sizes = Flux([{"size": "S"}, {"size": "M"}])

    res = colors.cross_join(sizes).collect()

    assert len(res) == 4
    assert res[0] == {"color": "red", "size": "S"}
    assert res[1] == {"color": "red", "size": "M"}
    assert res[2] == {"color": "blue", "size": "S"}
    assert res[3] == {"color": "blue", "size": "M"}


def test_optimizer_skip_collapse():
    # skip(5).skip(10) -> skip(15)
    pipeline = Flux(range(30)).skip(5).skip(10).optimize()
    plan_str = pipeline.explain()

    assert "SKIP: 15" in plan_str
    assert pipeline.first() == 15


def test_optimizer_take_zero_elimination():
    pipeline = Flux(range(100)).take(0)
    assert pipeline.collect() == []
    assert pipeline.explain(optimized=True).count("SOURCE: list") == 1