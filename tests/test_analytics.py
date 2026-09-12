import pytest
from fluxmonad import Flux


def test_enumerate_tuples_and_field():
    items = ["a", "b", "c"]
    assert Flux(items).enumerate(start=1).collect() == [(1, "a"), (2, "b"), (3, "c")]

    records = [{"item": "apple"}, {"item": "banana"}]
    res = Flux(records).enumerate(start=10, field="row_num").collect()
    assert res == [
        {"item": "apple", "row_num": 10},
        {"item": "banana", "row_num": 11},
    ]


def test_cumulative_sum():
    orders = [
        {"day": 1, "revenue": 100},
        {"day": 2, "revenue": 150},
        {"day": 3, "revenue": 50},
    ]
    res = Flux(orders).cumulative_sum("revenue", target_field="running_total").collect()

    assert res == [
        {"day": 1, "revenue": 100, "running_total": 100},
        {"day": 2, "revenue": 150, "running_total": 250},
        {"day": 3, "revenue": 50, "running_total": 300},
    ]


def test_lag_and_lead():
    data = [
        {"val": 10},
        {"val": 20},
        {"val": 30},
    ]

    # LAG: предыдущее значение
    lag_res = Flux(data).lag("val", offset=1, default=0).collect()
    assert [x["val_lag1"] for x in lag_res] == [0, 10, 20]

    # LEAD: следующее значение
    lead_res = Flux(data).lead("val", offset=1, default=999).collect()
    assert [x["val_lead1"] for x in lead_res] == [20, 30, 999]


def test_statistics_median_mode_stddev():
    numbers = Flux([1, 2, 2, 3, 4, 7, 9])

    assert numbers.median() == 3.0
    assert numbers.mode() == 2
    assert round(numbers.std_dev(), 2) == 2.94

    # Проверка через выборку поля
    rows = Flux([{"val": 10}, {"val": 20}, {"val": 30}])
    assert rows.median("val") == 20.0