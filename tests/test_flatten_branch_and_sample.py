from fluxmonad import Flux


def test_flatten_root():
    nested = [[1, 2], [3], [4, 5]]
    assert Flux(nested).flatten().collect() == [1, 2, 3, 4, 5]


def test_flatten_field():
    orders = [
        {"order_id": 101, "tags": ["sale", "promo"]},
        {"order_id": 102, "tags": ["new"]},
    ]
    exploded = Flux(orders).flatten("tags").collect()
    assert exploded == [
        {"order_id": 101, "tags": "sale"},
        {"order_id": 101, "tags": "promo"},
        {"order_id": 102, "tags": "new"},
    ]


def test_fill_null():
    records = [
        {"name": "Alice", "city": None},
        {"name": "Bob", "city": "Berlin"},
    ]
    res = Flux(records).fill_null(city="Unknown").collect()
    assert res == [
        {"name": "Alice", "city": "Unknown"},
        {"name": "Bob", "city": "Berlin"},
    ]


def test_branch():
    data = [1, 2, 3, 4]
    # Чётные умножаем на 10, нечётные оставляем как есть
    res = (
        Flux(data)
        .branch(
            lambda x: x % 2 == 0,
            if_true=lambda x: x * 10,
            if_false=lambda x: x,
        )
        .collect()
    )
    assert res == [1, 20, 3, 40]


def test_sample_reservoir_deterministic():
    data = list(range(100))
    sample1 = Flux(data).sample(5, seed=42).collect()
    sample2 = Flux(data).sample(5, seed=42).collect()

    assert len(sample1) == 5
    assert sample1 == sample2
    assert all(x in data for x in sample1)