from dataclasses import dataclass
import pytest
from fluxmonad.accessors import get_value, has_path, parse_path, project_exclude, project_select
from fluxmonad.accessors.resolver import MISSING


@dataclass
class Address:
    city: str
    zip_code: int


class User:
    def __init__(self, name: str, address: Address):
        self.name = name
        self.address = address


def test_parse_path_valid():
    assert parse_path("user.profile.name") == ["user", "profile", "name"]
    assert parse_path("name") == ["name"]


def test_parse_path_invalid():
    with pytest.raises(ValueError):
        parse_path("")
    with pytest.raises(ValueError):
        parse_path("user..name")


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