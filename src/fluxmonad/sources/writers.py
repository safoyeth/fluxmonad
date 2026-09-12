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

def write_yaml(
    items: Iterable[Any],
    filepath: Union[str, Path],
    encoding: str = "utf-8",
) -> None:
    """Записывает элементы потока в YAML-файл (требуется PyYAML)."""
    try:
        import yaml
    except ImportError:
        raise ImportError("Для записи YAML необходимо установить PyYAML: pip install pyyaml")

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = list(items)
    with open(path, mode="w", encoding=encoding) as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def write_toml(
    items: Iterable[Any],
    filepath: Union[str, Path],
    root_key: str = "items",
    encoding: str = "utf-8",
) -> None:
    """
    Записывает элементы потока в TOML-файл.
    Поскольку TOML верхнеуровнево требует таблицу (key-value),
    список элементов помещается под ключ `root_key` (по умолчанию 'items'),
    либо записывается напрямую, если поток состоит из одной структуры-словаря.
    Требуется tomli-w (или rtoml).
    """
    try:
        import tomli_w
        dump_fn = tomli_w.dump
    except ImportError:
        try:
            import rtoml  # pyright: ignore[reportMissingImports]
            dump_fn = None
        except ImportError:
            raise ImportError("Для записи TOML необходимо установить tomli-w: pip install tomli-w")

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = list(items)
    # Если передан ровно один словарь, сохраняем его корневым документом
    payload = data[0] if len(data) == 1 and isinstance(data[0], dict) else {root_key: data}

    if dump_fn is not None:
        with open(path, mode="wb") as f:
            dump_fn(payload, f)
    else:
        import rtoml  # pyright: ignore[reportMissingImports]
        rtoml.dump(payload, path)


def write_excel(
    items: Iterable[Any],
    filepath: Union[str, Path],
    sheet_name: str = "Sheet1",
) -> None:
    """Записывает словари или объекты потока в Excel (.xlsx) через openpyxl."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Для записи Excel (.xlsx) необходимо установить openpyxl: pip install openpyxl")

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    iterator = iter(items)
    try:
        first_row = next(iterator)
    except StopIteration:
        wb = openpyxl.Workbook()
        wb.save(path)
        wb.close()
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    if isinstance(first_row, dict):
        headers = list(first_row.keys())
        first_values = [first_row[h] for h in headers]
    elif hasattr(first_row, "__dict__"):
        headers = [k for k in first_row.__dict__.keys() if not k.startswith("_")]
        first_values = [getattr(first_row, h) for h in headers]
    else:
        headers = ["value"]
        first_values = [first_row]

    ws.append(headers)
    ws.append(first_values)

    for row in iterator:
        if isinstance(row, dict):
            ws.append([row.get(h) for h in headers])
        elif hasattr(row, "__dict__"):
            ws.append([getattr(row, h, None) for h in headers])
        else:
            ws.append([row])

    wb.save(path)
    wb.close()