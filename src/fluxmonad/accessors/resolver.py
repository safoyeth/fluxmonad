from collections.abc import Mapping, Sequence
from typing import Any

from fluxmonad.accessors.path import parse_path

MISSING = object()


def resolve_step(obj: Any, token: str) -> Any:
    """Извлекает один шаг пути из объекта (без рекурсии)."""
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
    Рекурсивно обходит структуру (DFS) и возвращает
    первое найденное значение для target_key.
    """
    if obj is None:
        return MISSING

    # 1. Проверяем текущий уровень
    val = resolve_step(obj, target_key)
    if val is not MISSING:
        return val

    # 2. Если словарь — спускаемся по значениям
    if isinstance(obj, Mapping):
        for v in obj.values():
            found = find_deep_value(v, target_key)
            if found is not MISSING:
                return found

    # 3. Если последовательность (список/кортеж) — спускаемся по элементам
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        for item in obj:
            found = find_deep_value(item, target_key)
            if found is not MISSING:
                return found

    # 4. Если объект с __dict__ — обходим атрибуты
    elif hasattr(obj, "__dict__"):
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                found = find_deep_value(v, target_key)
                if found is not MISSING:
                    return found

    return MISSING


def get_value(obj: Any, path: str, default: Any = MISSING) -> Any:
    """
    Универсально извлекает значение из объекта по строковому пути.
    Поддерживает явный синтаксис глубокого поиска: '..key' или 'path..key'.
    """
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
    """Проверяет существование пути в объекте."""
    return get_value(obj, path, default=MISSING) is not MISSING