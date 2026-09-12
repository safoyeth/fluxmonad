from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PathSegment:
    name: str
    is_deep: bool = False  # True, если сегменту предшествовал маркер '..'


def parse_path(path: str) -> List[PathSegment]:
    """
    Разбирает строковый путь на сегменты с поддержкой маркера глубокого поиска '..'.
    Примеры:
      'name'             -> [PathSegment('name', is_deep=False)]
      '..inner'          -> [PathSegment('inner', is_deep=True)]
      'test.2..inner'    -> [PathSegment('test'), PathSegment('2'), PathSegment('inner', is_deep=True)]
    """
    if not path or not isinstance(path, str):
        raise ValueError("Путь должен быть непустой строкой")

    segments: List[PathSegment] = []
    i = 0
    n = len(path)

    while i < n:
        is_deep = False
        if path[i:i + 2] == "..":
            is_deep = True
            i += 2
        elif path[i] == ".":
            i += 1

        if i >= n:
            raise ValueError(f"Некорректный путь: неожиданный конец после точки в '{path}'")

        # Читаем имя сегмента до следующей точки
        start = i
        while i < n and path[i] != ".":
            i += 1

        token = path[start:i].strip()
        if not token:
            raise ValueError(f"Пустой сегмент в пути: '{path}'")

        segments.append(PathSegment(name=token, is_deep=is_deep))

    return segments