from fluxmonad.expressions import Field, build_expression


def test_field_operators():
    user = {"name": "Ivan", "age": 25, "tags": ["admin", "staff"]}

    expr_gte = Field("age") >= 18
    expr_lt = Field("age") < 20
    expr_in = Field("name").is_in(["Ivan", "Petr"])
    expr_contains = Field("tags").contains("admin")

    assert expr_gte.evaluate(user) is True
    assert expr_lt.evaluate(user) is False
    assert expr_in.evaluate(user) is True
    assert expr_contains.evaluate(user) is True


def test_logical_combinators():
    user = {"name": "Ivan", "age": 25}

    expr_and = (Field("age") >= 18) & (Field("name") == "Ivan")
    expr_or = (Field("age") > 30) | (Field("name") == "Ivan")
    expr_not = ~(Field("age") > 30)

    assert expr_and.evaluate(user) is True
    assert expr_or.evaluate(user) is True
    assert expr_not.evaluate(user) is True
    assert expr_and.explain() == "(age >= 18 AND name == 'Ivan')"


def test_kwargs_parser():
    user = {"profile": {"age": 20}, "status": "active"}

    expr = build_expression(profile__age__gte=18, status="active")
    assert expr.evaluate(user) is True

    bad_user = {"profile": {"age": 16}, "status": "active"}
    assert expr.evaluate(bad_user) is False


def test_mixed_callable_and_kwargs():
    user = {"age": 25, "active": True}

    expr = build_expression(lambda u: u["age"] % 5 == 0, active=True)
    assert expr.evaluate(user) is True