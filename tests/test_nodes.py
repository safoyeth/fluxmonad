import pytest
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import FilterNode, MapNode, TakeNode


def test_source_node_evaluation():
    data = [1, 2, 3]
    node = SourceNode(data)
    assert not node.is_barrier
    assert list(node.evaluate()) == [1, 2, 3]
    assert node.explain_step() == "SOURCE: list"


def test_pipeline_lazy_evaluation():
    # Проверяем, что вычисления не запускаются до evaluate()
    called = []

    def tracking_map(x: int) -> int:
        called.append(x)
        return x * 2

    source = SourceNode([1, 2, 3, 4, 5])
    map_node = MapNode(source, tracking_map)
    take_node = TakeNode(map_node, 2)

    assert called == [], "План не должен исполняться при инициализации узлов"

    result = list(take_node.evaluate())
    assert result == [2, 4]
    # Благодаря short-circuiting обработано ровно 2 элемента, а не все 5
    assert called == [1, 2]


def test_infinite_generator_with_take():
    def infinite_counter():
        n = 0
        while True:
            yield n
            n += 1

    source = SourceNode(infinite_counter())
    even_filter = FilterNode(source, lambda x: x % 2 == 0)
    take_node = TakeNode(even_filter, 5)

    # Должен завершиться без зависания
    assert list(take_node.evaluate()) == [0, 2, 4, 6, 8]


def test_take_negative_count_raises_value_error():
    source = SourceNode([1, 2, 3])
    with pytest.raises(ValueError):
        TakeNode(source, -1)