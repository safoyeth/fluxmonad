from typing import Any, List
from fluxmonad.expressions.base import Expression

class And(Expression):
    def __init__(self, *expressions: Expression) -> None:
        self.expressions = list(expressions)

    @property
    def referenced_fields(self) -> set[str]:
        res: set[str] = set()
        for expr in self.expressions:
            res.update(expr.referenced_fields)
        return res

    def evaluate(self, item: Any) -> bool:
        return all(expr.evaluate(item) for expr in self.expressions)

    def explain(self) -> str:
        inner = " AND ".join(e.explain() if hasattr(e, "explain") else str(e) for e in self.expressions)
        return f"({inner})"


class Or(Expression):
    def __init__(self, *expressions: Expression) -> None:
        self.expressions = list(expressions)

    @property
    def referenced_fields(self) -> set[str]:
        res: set[str] = set()
        for expr in self.expressions:
            res.update(expr.referenced_fields)
        return res

    def evaluate(self, item: Any) -> bool:
        return any(expr.evaluate(item) for expr in self.expressions)

    def explain(self) -> str:
        inner = " OR ".join(e.explain() if hasattr(e, "explain") else str(e) for e in self.expressions)
        return f"({inner})"


class Not(Expression):
    def __init__(self, expression: Expression) -> None:
        self.expression = expression

    @property
    def referenced_fields(self) -> set[str]:
        return self.expression.referenced_fields

    def evaluate(self, item: Any) -> bool:
        return not self.expression.evaluate(item)

    def explain(self) -> str:
        inner = self.expression.explain() if hasattr(self.expression, "explain") else str(self.expression)
        return f"NOT({inner})"

def and_(*expressions: Expression) -> Expression:
    """Объединяет выражения через логическое И: and_(expr1, expr2)."""
    return And(*expressions)


def or_(*expressions: Expression) -> Expression:
    """Объединяет выражения через логическое ИЛИ: or_(expr1, expr2)."""
    return Or(*expressions)


def not_(expression: Expression) -> Expression:
    """Инвертирует выражение: not_(expr)."""
    return Not(expression)