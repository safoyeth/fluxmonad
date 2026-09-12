from fluxmonad import Field, Flux, Q, and_, not_, or_


def test_or_function_combinator():
    users = [
        {"name": "Alice", "age": 70, "role": "guest"},
        {"name": "Bob", "age": 30, "role": "vip"},
        {"name": "Charlie", "age": 25, "role": "guest"},
    ]

    # Использование функции or_()
    res = (
        Flux(users)
        .when(or_(Field("age") >= 65, Field("role") == "vip"))
        .select("name")
        .collect()
    )
    assert res == [{"name": "Alice"}, {"name": "Bob"}]


def test_method_chain_or():
    users = [
        {"status": "banned"},
        {"status": "pending"},
        {"status": "active"},
    ]

    # Использование метода .or_()
    res = (
        Flux(users)
        .when((Field("status") == "banned").or_(Field("status") == "pending"))
        .collect()
    )
    assert res == [{"status": "banned"}, {"status": "pending"}]


def test_django_style_q_objects():
    users = [
        {"name": "Alice", "age": 17, "is_admin": True},
        {"name": "Bob", "age": 22, "is_admin": False},
        {"name": "Charlie", "age": 16, "is_admin": False},
    ]

    # Через оператор |
    res_operator = (
        Flux(users)
        .when(Q(age__gte=18) | Q(is_admin=True))
        .select("name")
        .collect()
    )
    assert res_operator == [{"name": "Alice"}, {"name": "Bob"}]

    # Через словесный .or_()
    res_word = (
        Flux(users)
        .when(Q(age__gte=18).or_(Q(is_admin=True)))
        .select("name")
        .collect()
    )
    assert res_word == [{"name": "Alice"}, {"name": "Bob"}]


def test_q_negation():
    items = [{"val": 10}, {"val": 20}, {"val": 30}]
    res = Flux(items).when(~Q(val=20)).collect()
    assert res == [{"val": 10}, {"val": 30}]