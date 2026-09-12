from typing import Any, Callable, Dict, Type, Union
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.fields import Contains, Eq, Gt, Gte, In, Lt, Lte, Ne
from fluxmonad.expressions.logical import And

OPERATORS: Dict[str, Type[Expression]] = {
    "exact": Eq,
    "eq": Eq,
    "ne": Ne,
    "gt": Gt,
    "gte": Gte,
    "lt": Lt,
    "lte": Lte,
    "in": In,
    "contains": Contains,
}


class LambdaExpression(Expression):
    """Обёртка над обычной Python callable-функцией для единообразия в дереве выражений."""

    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self.predicate = predicate

    def evaluate(self, obj: Any) -> bool:
        return bool(self.predicate(obj))

    def explain(self) -> str:
        return getattr(self.predicate, "__name__", str(self.predicate))


def parse_lookup(key: str, value: Any) -> Expression:
    """
    Разбирает пару key=value.
    Примеры:
      'age__gte' -> Gte('age', value)
      'user__name' -> Eq('user.name', value)
      'status' -> Eq('status', value)
    """
    tokens = key.split("__")

    if len(tokens) > 1 and tokens[-1] in OPERATORS:
        op_name = tokens[-1]
        field_path = ".".join(tokens[:-1])
        op_cls = OPERATORS[op_name]
        return op_cls(field_path, value)  # type: ignore[call-arg]

    field_path = ".".join(tokens)
    return Eq(field_path, value)


def build_expression(
    predicate: Union[None, Callable[[Any], bool], Expression] = None,
    **kwargs: Any,
) -> Expression:
    """Объединяет позиционный предикат/Expression и именованные kwargs через And."""
    expressions: list[Expression] = []

    if predicate is not None:
        if isinstance(predicate, Expression):
            expressions.append(predicate)
        elif callable(predicate):
            expressions.append(LambdaExpression(predicate))
        else:
            raise TypeError(f"Предикат должен быть Callable или Expression, получен: {type(predicate)}")

    for key, val in kwargs.items():
        expressions.append(parse_lookup(key, val))

    if not expressions:
        raise ValueError("Для фильтрации не передано ни одного условия")

    if len(expressions) == 1:
        return expressions[0]

    return And(*expressions)