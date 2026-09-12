import pytest
from fluxmonad import Flux


def test_flux_identity_collect():
    data = [1, 2, 3, 4]
    flux = Flux(data)
    assert flux.collect() == data
    assert list(flux) == data


def test_flux_immutability():
    a = Flux([1, 2, 3, 4, 5])
    b = a.filter(lambda x: x > 2)
    c = b.map(lambda x: x * 10)
    d = c.take(2)

    # Исходные инстансы независимы и не изменились
    assert a.collect() == [1, 2, 3, 4, 5]
    assert b.collect() == [3, 4, 5]
    assert c.collect() == [30, 40, 50]
    assert d.collect() == [30, 40]


def test_flux_bind_and_rshift_operator():
    data = [1, 2, 3]
    # bind возвращает список из двух элементов для каждого x
    f = lambda x: [x, x * 10]

    # Проверка через метод bind
    result_bind = Flux(data).bind(f).collect()
    assert result_bind == [1, 10, 2, 20, 3, 30]

    # Проверка через оператор >>
    result_shift = (Flux(data) >> f).collect()
    assert result_shift == [1, 10, 2, 20, 3, 30]


def test_flux_bind_with_nested_flux():
    data = [1, 2]
    # Функция возвращает другой Flux
    f = lambda x: Flux([f"a{x}", f"b{x}"])

    result = (Flux(data) >> f).collect()
    assert result == ["a1", "b1", "a2", "b2"]


def test_flux_chained_rshift():
    data = [1, 2]
    add_pair = lambda x: [x, -x]
    to_str = lambda x: [str(x)]

    result = (Flux(data) >> add_pair >> to_str).collect()
    assert result == ["1", "-1", "2", "-2"]


def test_flux_first_and_count():
    flux = Flux([10, 20, 30])
    assert flux.first() == 10
    assert flux.count() == 3

    empty_flux = Flux([])
    assert empty_flux.first() is None
    assert empty_flux.first(default=-1) == -1
    assert empty_flux.count() == 0


def test_flux_infinite_lazy_pipeline():
    def natural_numbers():
        n = 1
        while True:
            yield n
            n += 1

    # Бесконечный генератор -> фильтр нечетных -> умножение -> взять 3
    result = (
        Flux(natural_numbers())
        .filter(lambda x: x % 2 != 0)
        .map(lambda x: x * 10)
        .take(3)
        .collect()
    )
    assert result == [10, 30, 50]