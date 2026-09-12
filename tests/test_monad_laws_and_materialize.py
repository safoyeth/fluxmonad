from fluxmonad import Flux


def test_materialize_reusable_iteration():
    # Одноразовый генератор, который исчерпывается после первого прохода
    def single_use_gen():
        for i in range(3):
            yield i

    stream = Flux(single_use_gen())
    materialized = stream.materialize()

    # Первый проход
    assert materialized.collect() == [0, 1, 2]
    # Второй проход по тому же объекту: данные не потерялись
    assert materialized.collect() == [0, 1, 2]
    assert materialized.count() == 3


def test_monad_left_identity():
    # Law 1: return a >>= f  ===  f a
    a = 5
    f = lambda x: Flux([x, x * 2])

    left = (Flux([a]) >> f).collect()
    right = f(a).collect()

    assert left == right == [5, 10]


def test_monad_right_identity():
    # Law 2: m >>= return  ===  m
    m_data = [1, 2, 3]
    m = Flux(m_data)
    unit = lambda x: Flux([x])

    res = (m >> unit).collect()
    assert res == m_data


def test_monad_associativity():
    # Law 3: (m >>= f) >>= g  ===  m >>= (\x -> f x >>= g)
    data = [1, 2]
    f = lambda x: Flux([x, x + 10])
    g = lambda x: Flux([x * 2])

    left = ((Flux(data) >> f) >> g).collect()
    right = (Flux(data) >> (lambda x: f(x) >> g)).collect()

    assert left == right == [2, 22, 4, 24]