from dataclasses import dataclass
from fluxmonad import Field, Flux


@dataclass
class User:
    name: str
    age: int
    role: str


def test_when_kwargs_filter():
    data = [
        {"name": "Alice", "age": 17, "city": "London"},
        {"name": "Bob", "age": 25, "city": "Paris"},
        {"name": "Charlie", "age": 30, "city": "London"},
    ]

    result = (
        Flux(data)
        .when(age__gte=18, city="London")
        .collect()
    )
    assert result == [{"name": "Charlie", "age": 30, "city": "London"}]


def test_when_field_expression():
    data = [
        User("Alice", 17, "user"),
        User("Bob", 22, "admin"),
        User("Charlie", 40, "moderator"),
    ]

    result = (
        Flux(data)
        .when((Field("age") >= 18) & (Field("role") == "admin"))
        .collect()
    )
    assert len(result) == 1
    assert result[0].name == "Bob"


def test_select_projection():
    users = [
        {"name": "Alice", "age": 25, "password": "hash1", "city": "London"},
        {"name": "Bob", "age": 30, "password": "hash2", "city": "Paris"},
    ]

    # Передача строками через запятую
    res1 = Flux(users).select("name", "age").collect()
    assert res1 == [
        {"name": "Alice", "age": 25},
        {"name": "Bob", "age": 30},
    ]

    # Передача списком
    res2 = Flux(users).select(["city"]).collect()
    assert res2 == [{"city": "London"}, {"city": "Paris"}]


def test_exclude_projection():
    users = [
        {"name": "Alice", "password": "123", "token": "abc"},
        {"name": "Bob", "password": "456", "token": "def"},
    ]

    result = Flux(users).exclude("password", "token").collect()
    assert result == [
        {"name": "Alice"},
        {"name": "Bob"},
    ]


def test_chained_dsl_pipeline():
    data = [
        {"name": "Ivan", "age": 16, "secret": "s1"},
        {"name": "Anna", "age": 21, "secret": "s2"},
        {"name": "Sergey", "age": 35, "secret": "s3"},
    ]

    result = (
        Flux(data)
        .when(age__gte=18)
        .exclude("secret")
        .take(1)
        .collect()
    )

    assert result == [{"name": "Anna", "age": 21}]