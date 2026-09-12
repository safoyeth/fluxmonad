from typing import Any, Set
from fluxmonad.accessors import MISSING, get_value
from fluxmonad.expressions.base import Expression


class BinaryOp(Expression):
    """Бинарная операция сравнения значения поля с константой."""

    def __init__(self, field_path: str, value: Any, op_name: str) -> None:
        self.field_path = field_path
        self.value = value
        self.op_name = op_name
        self._is_simple = isinstance(field_path, str) and "." not in field_path

    def _get_value(self, obj: Any) -> Any:
        if self._is_simple and isinstance(obj, dict):
            return obj.get(self.field_path, MISSING)
        return get_value(obj, self.field_path, default=MISSING)

    @property
    def referenced_fields(self) -> Set[str]:
        fields: Set[str] = set()
        if isinstance(self.field_path, str):
            fields.add(self.field_path.split(".")[0].strip())
        elif hasattr(self.field_path, "path"):
            fields.add(str(self.field_path.path).split(".")[0].strip())

        if hasattr(self.value, "referenced_fields"):
            try:
                rf = self.value.referenced_fields
                if rf:
                    fields.update(rf)
            except Exception:
                pass
        elif hasattr(self.value, "path") and not isinstance(self.value, (str, bytes)):
            fields.add(str(self.value.path).split(".")[0].strip())
        return fields

    def explain(self) -> str:
        return f"{self.field_path} {self.op_name} {repr(self.value)}"


class Eq(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "==")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        return False if val is MISSING else bool(val == self.value)


class Ne(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "!=")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        return False if val is MISSING else bool(val != self.value)


class Gt(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, ">")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING or val is None:
            return False
        try:
            return bool(val > self.value)
        except TypeError:
            return False


class Gte(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, ">=")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING or val is None:
            return False
        try:
            return bool(val >= self.value)
        except TypeError:
            return False


class Lt(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "<")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING or val is None:
            return False
        try:
            return bool(val < self.value)
        except TypeError:
            return False


class Lte(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "<=")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING or val is None:
            return False
        try:
            return bool(val <= self.value)
        except TypeError:
            return False


class In(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "IN")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING:
            return False
        try:
            return bool(val in self.value)
        except TypeError:
            return False


class Contains(BinaryOp):
    def __init__(self, field_path: str, value: Any) -> None:
        super().__init__(field_path, value, "CONTAINS")

    def evaluate(self, obj: Any) -> bool:
        val = self._get_value(obj)
        if val is MISSING or val is None:
            return False
        try:
            return bool(self.value in val)
        except TypeError:
            return False


class Field:
    """Дескриптор поля для построения выражений в коде: Field('age') >= 18."""

    def __init__(self, path: str) -> None:
        self.path = path

    @property
    def referenced_fields(self) -> Set[str]:
        return {self.path.split(".")[0].strip()}

    def __eq__(self, other: Any) -> Eq:  # type: ignore[override]
        return Eq(self.path, other)

    def __ne__(self, other: Any) -> Ne:  # type: ignore[override]
        return Ne(self.path, other)

    def __gt__(self, other: Any) -> Gt:
        return Gt(self.path, other)

    def __ge__(self, other: Any) -> Gte:
        return Gte(self.path, other)

    def __lt__(self, other: Any) -> Lt:
        return Lt(self.path, other)

    def __le__(self, other: Any) -> Lte:
        return Lte(self.path, other)

    def is_in(self, values: Any) -> In:
        return In(self.path, values)

    def contains(self, value: Any) -> Contains:
        return Contains(self.path, value)