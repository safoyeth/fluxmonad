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
    def __init__(self, func: Callable[[Any], bool]) -> None:
        self.func = func

    def evaluate(self, item: Any) -> bool:
        return bool(self.func(item))

    def explain(self) -> str:
        name = getattr(self.func, "__name__", "<lambda>")
        return f"LAMBDA: {name}"

    @property
    def referenced_fields(self) -> set[str]:
        # Scalar functions operating on the entire item have no explicit dictionary key dependencies
        return set()

class Q:
    """
    Declarative query builder inspired by Django ORM.
    Supports: Q(age__gte=18) | Q(role="admin")
    or: Q(age__gte=18).or_(Q(role="admin"))
    """

    def __init__(self, *args: Union[Expression, "Q"], **kwargs: Any) -> None:
        exprs: list[Expression] = []
        for arg in args:
            if isinstance(arg, Q):
                exprs.append(arg.expr)
            elif isinstance(arg, Expression):
                exprs.append(arg)
            else:
                raise TypeError(f"Unsupported argument type in Q: {type(arg)}")

        for k, v in kwargs.items():
            exprs.append(parse_lookup(k, v))

        if not exprs:
            raise ValueError("Q object requires at least one argument or keyword argument")

        self.expr: Expression = exprs[0] if len(exprs) == 1 else And(*exprs)

    def __or__(self, other: Union["Q", Expression]) -> "Q":
        other_expr = other.expr if isinstance(other, Q) else other
        return Q(self.expr | other_expr)

    def __and__(self, other: Union["Q", Expression]) -> "Q":
        other_expr = other.expr if isinstance(other, Q) else other
        return Q(self.expr & other_expr)

    def __invert__(self) -> "Q":
        return Q(~self.expr)

    def or_(self, other: Union["Q", Expression]) -> "Q":
        return self | other

    def and_(self, other: Union["Q", Expression]) -> "Q":
        return self & other


def parse_lookup(key: str, value: Any) -> Expression:
    """
    Parses a key=value pair into an Expression.
    Examples:
      'age__gte'   -> Gte('age', value)
      'user__name' -> Eq('user.name', value)
      'status'     -> Eq('status', value)
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
    predicate: Union[None, Callable[[Any], bool], Expression, Q] = None,
    **kwargs: Any,
) -> Expression:
    expressions: list[Expression] = []

    if predicate is not None:
        if isinstance(predicate, Q):
            expressions.append(predicate.expr)
        elif isinstance(predicate, Expression):
            expressions.append(predicate)
        elif callable(predicate):
            expressions.append(LambdaExpression(predicate))
        else:
            raise TypeError(f"Predicate must be Callable, Expression, or Q; got {type(predicate)}")

    for key, val in kwargs.items():
        expressions.append(parse_lookup(key, val))

    if not expressions:
        raise ValueError("No filter conditions provided")

    if len(expressions) == 1:
        return expressions[0]

    return And(*expressions)
