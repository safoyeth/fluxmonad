from collections.abc import Mapping
from typing import Any, Dict, Iterable, Sequence

from fluxmonad.accessors.resolver import MISSING, get_value


def project_select(obj: Any, fields: Sequence[str]) -> Dict[str, Any]:
    """
    Проецирует объект, оставляя только указанные поля.
    Поля сохраняются в виде словаря {field: value}.
    """
    result: Dict[str, Any] = {}
    for field in fields:
        val = get_value(obj, field, default=None)
        # Имя ключа в результирующем словаре — последнее имя пути или исходное
        key = field.split(".")[-1] if "." in field else field
        result[key] = val
    return result


def project_exclude(obj: Any, fields: Iterable[str]) -> Dict[str, Any]:
    """
    Исключает указанные поля из объекта.
    Если объект — Mapping, возвращает копию словаря без исключённых ключей.
    Если объект — класс с __dict__, возвращает словарь его атрибутов без исключённых ключей.
    """
    fields_set = set(fields)

    if isinstance(obj, Mapping):
        return {k: v for k, v in obj.items() if k not in fields_set}

    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if k not in fields_set and not k.startswith("_")}

    return {}