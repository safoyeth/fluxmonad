import pytest
from fluxmonad import Flux


def test_sortby_single_field_and_descending():
    data = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 20},
        {"name": "Charlie", "age": 25},
    ]

    # Сортировка по возрастанию
    asc = Flux(data).sortby("age").collect()
    assert [x["name"] for x in asc] == ["Bob", "Charlie", "Alice"]

    # Сортировка по убыванию через синтаксис '-'
    desc = Flux(data).sortby("-age").collect()
    assert [x["name"] for x in desc] == ["Alice", "Charlie", "Bob"]


def test_sortby_multiple_fields():
    data = [
        {"dept": "IT", "salary": 100},
        {"dept": "HR", "salary": 80},
        {"dept": "IT", "salary": 120},
    ]

    # Сортировка сначала по отделу (возрастание), потом по зарплате (убывание)
    res = Flux(data).sortby("dept", "-salary").collect()
    assert res == [
        {"dept": "HR", "salary": 80},
        {"dept": "IT", "salary": 120},
        {"dept": "IT", "salary": 100},
    ]


def test_sortby_callable():
    data = ["bb", "a", "ccc"]
    res = Flux(data).sortby(len).collect()
    assert res == ["a", "bb", "ccc"]


def test_skip_and_head():
    data = [1, 2, 3, 4, 5]
    assert Flux(data).skip(2).collect() == [3, 4, 5]
    assert Flux(data).head(3).collect() == [1, 2, 3]


def test_tail_and_last():
    data = [1, 2, 3, 4, 5]
    assert Flux(data).tail(2).collect() == [4, 5]
    assert Flux(data).last() == 5
    assert Flux([]).last(default=-1) == -1


def test_any_all_exists():
    flux = Flux([2, 4, 6])
    assert flux.exists() is True
    assert flux.all(lambda x: x % 2 == 0) is True
    assert flux.any(lambda x: x == 4) is True
    assert flux.any(lambda x: x == 5) is False

    empty = Flux([])
    assert empty.exists() is False


def test_reduce():
    flux = Flux([1, 2, 3, 4])
    sum_val = flux.reduce(lambda acc, x: acc + x, 0)
    assert sum_val == 10

    mult_val = flux.reduce(lambda acc, x: acc * x)
    assert mult_val == 24