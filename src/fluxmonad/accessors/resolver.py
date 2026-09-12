from collections.abc import Mapping, Sequence
from typing import Any

from fluxmonad.accessors.path import parse_path

MISSING = object()


def resolve_step(obj: Any, token: str) -> Any:
    """Extracts a single path step from an object without recursion."""
    if obj is None:
        return MISSING

    if isinstance(obj, Mapping):
        if token in obj:
            return obj[token]
        if token.isdigit() and int(token) in obj:
            return obj[int(token)]

    if hasattr(obj, token):
        return getattr(obj, token)

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        try:
            index = int(token)
            if -len(obj) <= index < len(obj):
                return obj[index]
        except (ValueError, IndexError):
            pass

    return MISSING


def find_deep_value(obj: Any, target_key: str) -> Any:
    """
    Recursively traverses the data structure (DFS) and returns
    the first resolved value for target_key.
    """
    if obj is None:
        return MISSING

    # 1. Check current level
    val = resolve_step(obj, target_key)
    if val is not MISSING:
        return val

    # 2. If mapping — traverse values
    if isinstance(obj, Mapping):
        for v in obj.values():
            found = find_deep_value(v, target_key)
            if found is not MISSING:
                return found

    # 3. If sequence (list/tuple) — traverse elements
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        for item in obj:
            found = find_deep_value(item, target_key)
            if found is not MISSING:
                return found

    # 4. If object with __dict__ — traverse public attributes
    elif hasattr(obj, "__dict__"):
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                found = find_deep_value(v, target_key)
                if found is not MISSING:
                    return found

    return MISSING


def get_value(obj: Any, path: str, default: Any = MISSING) -> Any:
    """
    Universally extracts a value from an object using a string path.
    Supports deep search syntax: '..key' or 'path..key'.
    """
    if obj is None:
        return default

    # Fast-path for simple keys without nesting or deep search
    if "." not in path:
        if isinstance(obj, dict):
            return obj.get(path, default)
        if isinstance(obj, Mapping):
            if path in obj:
                return obj[path]
            if path.isdigit() and int(path) in obj:
                return obj[int(path)]
        elif hasattr(obj, path):
            return getattr(obj, path)

    segments = parse_path(path)
    current = obj

    for seg in segments:
        if seg.is_deep:
            current = find_deep_value(current, seg.name)
        else:
            current = resolve_step(current, seg.name)

        if current is MISSING:
            return default

    return current


def has_path(obj: Any, path: str) -> bool:
    """Checks whether the specified path exists within the object."""
    return bool(get_value(obj, path, default=MISSING) is not MISSING)