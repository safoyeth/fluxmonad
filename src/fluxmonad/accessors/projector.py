from collections.abc import Mapping
from typing import Any, Dict, Iterable, Sequence

from fluxmonad.accessors.resolver import MISSING, get_value


def project_select(obj: Any, fields: Sequence[str]) -> Dict[str, Any]:
    """
    Projects an object, retaining only the specified fields.
    Fields are returned as a dictionary of {field: value}.
    """
    result: Dict[str, Any] = {}
    for field in fields:
        val = get_value(obj, field, default=None)
        # The key name in the resulting dict is the last path segment or original name
        key = field.split(".")[-1] if "." in field else field
        result[key] = val
    return result


def project_exclude(obj: Any, fields: Iterable[str]) -> Dict[str, Any]:
    """
    Excludes specified fields from an object.
    If the object is a Mapping, returns a copy of the dictionary without excluded keys.
    If the object has __dict__, returns a dictionary of its attributes without excluded keys.
    """
    fields_set = set(fields)

    if isinstance(obj, Mapping):
        return {k: v for k, v in obj.items() if k not in fields_set}

    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if k not in fields_set and not k.startswith("_")}

    return {}