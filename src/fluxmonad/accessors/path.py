import functools
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PathSegment:
    name: str
    is_deep: bool = False  # True if the segment was preceded by a deep search marker '..'


@functools.lru_cache(maxsize=1024)
def parse_path(path: str) -> List[PathSegment]:
    """
    Parses a string path into segments with support for deep search marker '..'.

    Examples:
      'name'             -> [PathSegment('name', is_deep=False)]
      '..inner'          -> [PathSegment('inner', is_deep=True)]
      'test.2..inner'    -> [PathSegment('test'), PathSegment('2'), PathSegment('inner', is_deep=True)]
    """
    if not path or not isinstance(path, str):
        raise ValueError("Path must be a non-empty string")

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
            raise ValueError(f"Invalid path: unexpected end after dot in '{path}'")

        # Read segment name until next dot
        start = i
        while i < n and path[i] != ".":
            i += 1

        token = path[start:i].strip()
        if not token:
            raise ValueError(f"Empty segment in path: '{path}'")

        segments.append(PathSegment(name=token, is_deep=is_deep))

    return segments