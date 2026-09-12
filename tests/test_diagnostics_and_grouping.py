from fluxmonad import Field, Flux


def test_explain_output():
    plan = (
        Flux([1, 2, 3, 4, 5])
        .when(Field("age") >= 18)
        .select("name", "age")
        .sortby("-age")
        .take(20)
    )

    explanation = plan.explain()

    assert "Flux execution plan" in explanation
    assert "SOURCE: list" in explanation
    assert "FILTER: age >= 18" in explanation
    assert "SELECT: name, age" in explanation
    assert "SORT: -age (barrier=True)" in explanation
    assert "TAKE: 20" in explanation


def test_groupby_by_field():
    users = [
        {"name": "Alice", "dept": "IT"},
        {"name": "Bob", "dept": "HR"},
        {"name": "Charlie", "dept": "IT"},
    ]

    groups = Flux(users).groupby("dept").collect()

    assert len(groups) == 2
    it_group = groups[0]
    hr_group = groups[1]

    assert it_group.key == "IT"
    assert len(it_group) == 2
    assert it_group.flux.select("name").collect() == [{"name": "Alice"}, {"name": "Charlie"}]

    assert hr_group.key == "HR"
    assert len(hr_group) == 1
    assert hr_group.flux.select("name").collect() == [{"name": "Bob"}]


def test_groupby_by_callable():
    numbers = [1, 2, 3, 4, 5, 6]
    # Группировка по четности
    groups = (
        Flux(numbers)
        .groupby(lambda x: "even" if x % 2 == 0 else "odd")
        .map(lambda g: {"parity": g.key, "sum": g.flux.reduce(lambda a, b: a + b)})
        .collect()
    )

    assert groups == [
        {"parity": "odd", "sum": 9},   # 1 + 3 + 5
        {"parity": "even", "sum": 12}, # 2 + 4 + 6
    ]