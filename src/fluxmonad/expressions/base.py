from abc import ABC, abstractmethod
from typing import Any


class Expression(ABC):
    """Базовое предикатное выражение."""

    @abstractmethod
    def evaluate(self, obj: Any) -> bool:
        """Вычисляет выражение для переданного объекта."""
        pass

    @abstractmethod
    def explain(self) -> str:
        """Возвращает читаемое строковое представление для плана выполнения."""
        pass

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
        """Логическое И (словесный метод)."""
        from fluxmonad.expressions.logical import And
        return And(self, other)

    def or_(self, other: "Expression") -> "Expression":
        """Логическое ИЛИ (словесный метод)."""
        from fluxmonad.expressions.logical import Or
        return Or(self, other)