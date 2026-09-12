from dataclasses import dataclass
import pytest
from fluxmonad.accessors import (
    MISSING,
    get_value,
    has_path,
    parse_path,
    project_exclude,
    project_select,
)
from fluxmonad.accessors.path import PathSegment


@dataclass
class Address:
    city: str
    zip_code: int


class User:
    def __init__(self, name: str, address: Address):
        self.name = name
        self.address = address


def test_parse_path_valid():
    assert parse_path("user.profile.name") == [
        PathSegment("user", is_deep=False),
        PathSegment("profile", is_deep=False),
        PathSegment("name", is_deep=False),
    ]
    assert parse_path("..inner") == [PathSegment("inner", is_deep=True)]
    assert parse_path("user..profile.name") == [
        PathSegment("user", is_deep=False),
        PathSegment("profile", is_deep=True),
        PathSegment("name", is_deep=False),
    ]


def test_parse_path_invalid():
    # Пустая строка
    with pytest.raises(ValueError):
        parse_path("")

    # Одиночная завершающая точка
    with pytest.raises(ValueError):
        parse_path("user.")

    # Тройная точка (некорректный синтаксис)
    with pytest.raises(ValueError):
        parse_path("user...name")


def test_get_value_dict():
    data = {"name": "Ivan", "meta": {"role": "admin", "tags": ["lead", "dev"]}}
    assert get_value(data, "name") == "Ivan"
    assert get_value(data, "meta.role") == "admin"
    assert get_value(data, "meta.tags.0") == "lead"
    assert get_value(data, "meta.tags.1") == "dev"


def test_get_value_objects():
    user = User("Alice", Address("London", 10001))
    assert get_value(user, "name") == "Alice"
    assert get_value(user, "address.city") == "London"
    assert get_value(user, "address.zip_code") == 10001


def test_get_value_mixed():
    mixed = {"user": User("Bob", Address("Paris", 75000)), "items": [{"id": 42}]}
    assert get_value(mixed, "user.name") == "Bob"
    assert get_value(mixed, "user.address.city") == "Paris"
    assert get_value(mixed, "items.0.id") == 42


def test_get_value_missing_and_default():
    data = {"name": "Ivan"}
    assert get_value(data, "unknown") is MISSING
    assert get_value(data, "unknown", default="N/A") == "N/A"
    assert not has_path(data, "unknown")
    assert has_path(data, "name")


def test_project_select():
    user = User("Alice", Address("London", 10001))
    result = project_select(user, ["name", "address.city"])
    assert result == {"name": "Alice", "city": "London"}


def test_project_exclude():
    data = {"name": "Ivan", "secret": "123", "age": 30}
    result = project_exclude(data, ["secret"])
    assert result == {"name": "Ivan", "age": 30}


def test_explicit_deep_search():
    data = [{"test": [2, 3, {"inner": "Here"}]}]

    assert get_value(data, "..inner") == "Here"
    assert get_value(data, "0.test..inner") == "Here"
    assert get_value(data, "inner", default="NOT_FOUND") == "NOT_FOUND"


def test_deep_search_in_objects_tree():
    class NodeItem:
        def __init__(self, value, child=None):
            self.value = value
            self.child = child

    tree = NodeItem("root", NodeItem("mid", {"target": "found_me"}))
    assert get_value(tree, "..target") == "found_me"