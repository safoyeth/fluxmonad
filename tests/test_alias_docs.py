from fluxmonad import Flux


def test_alias_docstrings_presence():
    # Проверяем, что алиас содержит пометку и docstring оригинального метода
    assert "Алиас для метода :meth:`sortby`" in Flux.sortBy.__doc__
    assert "Алиас для метода :meth:`sortby`" in Flux.sort_by.__doc__
    assert "Алиас для метода :meth:`collect`" in Flux.toList.__doc__
    assert "Алиас для метода :meth:`from_json`" in Flux.fromJson.__doc__


def test_alias_execution():
    data = [5, 2, 8, 1]
    res = Flux(data).sortBy().limit(2).toList()
    assert res == [1, 2]