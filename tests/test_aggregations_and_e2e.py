import pytest
from fluxmonad import Flux


def test_distinct_primitive_and_dict():
    data = [1, 2, 2, 3, 1, 4]
    assert Flux(data).distinct().collect() == [1, 2, 3, 4]

    # Нехешируемые словари
    dicts = [{"id": 1}, {"id": 2}, {"id": 1}]
    assert Flux(dicts).distinct("id").collect() == [{"id": 1}, {"id": 2}]


def test_aggregations():
    data = [
        {"name": "A", "score": 10},
        {"name": "B", "score": 20},
        {"name": "C", "score": 30},
    ]

    flux = Flux(data)
    assert flux.sum("score") == 60
    assert flux.average("score") == 20.0
    assert flux.min("score") == {"name": "A", "score": 10}
    assert flux.max("score") == {"name": "C", "score": 30}


def test_average_empty_raises():
    with pytest.raises(ValueError):
        Flux([]).average()


def test_tz_section_1_e2e_pipeline():
    """Проверка цепочки вызовов строго по примеру из ТЗ: Раздел 1."""
    data = [
        {"name": "Ivan", "age": 25, "department": "IT", "secret": "123"},
        {"name": "Olga", "age": 17, "department": "HR", "secret": "456"},
        {"name": "Petr", "age": 32, "department": "IT", "secret": "789"},
        {"name": "Anna", "age": 19, "department": "Finance", "secret": "000"},
    ]

    result = (
        Flux(data)
        .select("name", "age", "department")
        .exclude("department")
        .when(age__gte=18)
        .sortby("-age")
        .take(20)
        .collect()
    )

    # age__gte=18 отсекает Ольгу (17)
    # select оставляет name, age, department
    # exclude удаляет department -> остаются только name и age
    # sortby("-age") сортирует: Petr (32) -> Ivan (25) -> Anna (19)
    assert result == [
        {"name": "Petr", "age": 32},
        {"name": "Ivan", "age": 25},
        {"name": "Anna", "age": 19},
    ]