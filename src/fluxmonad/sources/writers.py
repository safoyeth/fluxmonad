import csv
import json
from pathlib import Path
from typing import Any, Iterable, Union


def write_json(
    items: Iterable[Any],
    filepath: Union[str, Path],
    lines: bool = False,
    indent: int = 2,
    encoding: str = "utf-8",
) -> None:
    """Записывает элементы потока в JSON или JSON Lines."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, mode="w", encoding=encoding) as f:
        if lines:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        else:
            data = list(items)
            json.dump(data, f, ensure_ascii=False, indent=indent)


def write_csv(
    items: Iterable[Any],
    filepath: Union[str, Path],
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> None:
    """Записывает словари или объекты потока в CSV файл."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    iterator = iter(items)
    try:
        first_row = next(iterator)
    except StopIteration:
        path.touch()
        return

    if isinstance(first_row, dict):
        fieldnames = list(first_row.keys())
    elif hasattr(first_row, "__dict__"):
        fieldnames = [k for k in first_row.__dict__.keys() if not k.startswith("_")]
    else:
        raise TypeError("Для записи в CSV элементы должны быть словарями или dataclass/объектами")

    with open(path, mode="w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerow(first_row if isinstance(first_row, dict) else first_row.__dict__)

        for row in iterator:
            writer.writerow(row if isinstance(row, dict) else row.__dict__)