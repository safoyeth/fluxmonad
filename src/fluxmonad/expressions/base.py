from abc import ABC, abstractmethod
from typing import Any


class Expression(ABC):
    @abstractmethod
    def evaluate(self, item: Any) -> bool:
        pass

    @property
    def referenced_fields(self) -> set[str]:
        """Set of fields required to evaluate this expression."""
        return set()

    def __and__(self, other: "Expression") -> "Expression":
        from fluxmonad.expressions.logical import And
        return And(self, other)

    def __or__(self, other: "Expression") -> "Expression":
        from fluxmonad.expressions.logical import Or
        return Or(self, other)

    def __invert__(self) -> "Expression":
        from fluxmonad.expressions.logical import Not
        return Not(self)

    def and_(self, other: "Expression") -> "Expression":
        from fluxmonad.expressions.logical import And
        return And(self, other)

    def or_(self, other: "Expression") -> "Expression":
        from fluxmonad.expressions.logical import Or
        return Or(self, other)

    @abstractmethod
    def explain(self) -> str:
        """String representation of the expression for the execution plan."""
        pass