from fluxmonad import Flux, Q


def test_reverse():
    data = [1, 2, 3, 4]
    assert Flux(data).reverse().collect() == [4, 3, 2, 1]


def test_tap_side_effects():
    logged = []
    pipeline = (
        Flux([1, 2, 3])
        .map(lambda x: x * 10)
        .tap(lambda x: logged.append(x))
        .take(2)
    )

    # До терминальной операции побочные эффекты не срабатывают (ленивость)
    assert logged == []

    result = pipeline.collect()
    assert result == [10, 20]
    assert logged == [10, 20]


def test_zip():
    names = Flux(["Alice", "Bob", "Charlie"])
    ages = Flux([25, 30, 35, 40])  # Четвертый элемент отсекается

    res = names.zip(ages).collect()
    assert res == [("Alice", 25), ("Bob", 30), ("Charlie", 35)]


def test_partition():
    users = [
        {"name": "Alice", "age": 20},
        {"name": "Bob", "age": 16},
        {"name": "Charlie", "age": 25},
    ]

    adults, minors = Flux(users).partition(age__gte=18)

    assert adults.select("name").collect() == [{"name": "Alice"}, {"name": "Charlie"}]
    assert minors.select("name").collect() == [{"name": "Bob"}]