from typing import Any, Callable, Optional, Set
from fluxmonad.expressions.base import Expression


class BinaryComparison(Expression):
    def __init__(self, left: Any, right: Any, op_str: str, op_func: Callable[[Any, Any], bool]) -> None:
        self.left = left
        self.right = right
        self.op_str = op_str
        self.op_func = op_func

    @property
    def referenced_fields(self) -> set[str]:
        fields: set[str] = set()
        
        # Левая часть — это имя проверяемого поля
        if isinstance(self.left, str):
            fields.add(self.left.split(".")[0].strip())
        elif hasattr(self.left, "path"):
            fields.add(str(self.left.path).split(".")[0].strip())
        elif hasattr(self.left, "name"):
            fields.add(str(self.left.name).split(".")[0].strip())

        # Правую часть берем ТОЛЬКО если это объект Field (сравнение двух полей)
        if hasattr(self.right, "path") and not isinstance(self.right, (str, bytes)):
            fields.add(str(self.right.path).split(".")[0].strip())
        elif hasattr(self.right, "name") and not isinstance(self.right, (str, bytes)):
            fields.add(str(self.right.name).split(".")[0].strip())

        return fields

    def evaluate(self, item: Any) -> bool:
        from fluxmonad.accessors import get_value
        field_name = self.left.path if hasattr(self.left, "path") else str(self.left)
        l_val = get_value(item, field_name)
        
        r_val = self.right
        if hasattr(r_val, "path"):
            r_val = get_value(item, r_val.path)

        if l_val is None:
            return False
        return self.op_func(l_val, r_val)

    def explain(self) -> str:
        left_str = self.left.path if hasattr(self.left, "path") else str(self.left)
        return f"{left_str} {self.op_str} {repr(self.right)}"


# Все операторы вызывают super().__init__ или сохраняют left/right
class Eq(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, "==", lambda a, b: a == b)


class Ne(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, "!=", lambda a, b: a != b)


class Gt(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, ">", lambda a, b: a > b)


class Gte(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, ">=", lambda a, b: a >= b)


class Lt(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, "<", lambda a, b: a < b)


class Lte(BinaryComparison):
    def __init__(self, left: Any, right: Any) -> None:
        super().__init__(left, right, "<=", lambda a, b: a <= b)