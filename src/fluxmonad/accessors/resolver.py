from collections.abc import Mapping, Sequence
from typing import Any, Optional

from fluxmonad.accessors.path import parse_path

# Специальный sentinel-объект для отличия реального None от отсутствующего значения
MISSING = object()


def resolve_step(obj: Any, token: str) -> Any:
    """Извлекает один шаг пути из объекта."""
    if obj is None:
        return MISSING

    # 1. Попытка доступа через Mapping (словарь)
    if isinstance(obj, Mapping):
        if token in obj:
            return obj[token]
        # Попытка целочисленного ключа для словарей со смешанными ключами
        if token.isdigit() and int(token) in obj:
            return obj[int(token)]

    # 2. Попытка доступа через атрибут объекта
    if hasattr(obj, token):
        return getattr(obj, token)

    # 3. Попытка доступа по индексу для списков/кортежей
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        try:
            index = int(token)
            if -len(obj) <= index < len(obj):
                return obj[index]
        except (ValueError, IndexError):
            pass

    return MISSING


def get_value(obj: Any, path: str, default: Any = MISSING) -> Any:
    """
    Универсально извлекает значение из произвольного Python-объекта по строковому пути.
    Поддерживает словари, объекты, списки/кортежи и вложенные цепочки вида 'a.b.0.c'.
    """
    tokens = parse_path(path)
    current = obj

    for token in tokens:
        current = resolve_step(current, token)
        if current is MISSING:
            return default

    return current


def has_path(obj: Any, path: str) -> bool:
    """Проверяет существование пути в объекте."""
    return get_value(obj, path, default=MISSING) is not MISSING