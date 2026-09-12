from typing import Any, List
from fluxmonad.expressions.base import Expression


class And(Expression):
    def __init__(self, *expressions: Expression) -> None:
        self.expressions: List[Expression] = []
        for expr in expressions:
            if isinstance(expr, And):
                self.expressions.extend(expr.expressions)
            else:
                self.expressions.append(expr)

    def evaluate(self, obj: Any) -> bool:
        return all(expr.evaluate(obj) for expr in self.expressions)

    def explain(self) -> str:
        return f"({' AND '.join(e.explain() for e in self.expressions)})"


class Or(Expression):
    def __init__(self, *expressions: Expression) -> None:
        self.expressions: List[Expression] = []
        for expr in expressions:
            if isinstance(expr, Or):
                self.expressions.extend(expr.expressions)
            else:
                self.expressions.append(expr)

    def evaluate(self, obj: Any) -> bool:
        return any(expr.evaluate(obj) for expr in self.expressions)

    def explain(self) -> str:
        return f"({' OR '.join(e.explain() for e in self.expressions)})"


class Not(Expression):
    def __init__(self, expression: Expression) -> None:
        self.expression = expression

    def evaluate(self, obj: Any) -> bool:
        return not self.expression.evaluate(obj)

    def explain(self) -> str:
        return f"NOT ({self.expression.explain()})"