from typing import List


def parse_path(path: str) -> List[str]:
    """
    Разбивает точечный путь на сегменты.
    Например: 'user.profile.name' -> ['user', 'profile', 'name'].
    """
    if not path or not isinstance(path, str):
        raise ValueError("Путь должен быть непустой строкой")

    tokens = [token.strip() for token in path.split(".")]
    if any(not token for token in tokens):
        raise ValueError(f"Некорректный путь к полю: '{path}'")

    return tokens