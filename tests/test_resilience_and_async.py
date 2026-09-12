import asyncio
from fluxmonad import Flux


def test_compact_removes_none():
    data = [1, None, 2, None, 3]
    assert Flux(data).compact().collect() == [1, 2, 3]


def test_catch_drop_errors():
    raw = ["10", "abc", "20", "xyz", "30"]

    # Преобразование int падает на "abc" и "xyz", catch отбрасывает сбойные элементы
    res = (
        Flux(raw)
        .map(int)
        .catch(exceptions=(ValueError,))
        .collect()
    )
    assert res == [10, 20, 30]


def test_catch_fallback_value():
    raw = ["10", "err", "30"]

    res = (
        Flux(raw)
        .map(int)
        .catch(handler=lambda exc, item: -1, exceptions=(ValueError,))
        .collect()
    )
    assert res == [10, -1, 30]


def test_async_iteration():
    async def _run():
        data = [10, 20, 30]
        flux = Flux(data).map(lambda x: x * 2)

        collected = []
        async for item in flux:
            collected.append(item)

        return collected

    assert asyncio.run(_run()) == [20, 40, 60]


def test_collect_async():
    async def _run():
        return await Flux([1, 2, 3]).map(lambda x: x + 1).collect_async()

    assert asyncio.run(_run()) == [2, 3, 4]