import csv
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Union


def read_json_source(
    path_or_str: Union[str, Path],
    lines: bool = False,
    encoding: str = "utf-8",
) -> Iterator[Any]:
    """Читает JSON-файл/строку (или JSON Lines при lines=True)."""
    target = Path(path_or_str) if isinstance(path_or_str, (str, Path)) and Path(path_or_str).is_file() else None

    if target:
        with open(target, mode="r", encoding=encoding) as f:
            if lines:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
            else:
                data = json.load(f)
                if isinstance(data, list):
                    yield from data
                else:
                    yield data
    else:
        # Парсинг чистой строки
        raw_str = str(path_or_str).strip()
        if lines:
            for line in raw_str.splitlines():
                if line.strip():
                    yield json.loads(line)
        else:
            data = json.loads(raw_str)
            if isinstance(data, list):
                yield from data
            else:
                yield data


def read_csv_source(
    filepath_or_buffer: Union[str, Path],
    encoding: str = "utf-8",
    delimiter: str = ",",
    fieldnames: Optional[list[str]] = None,
) -> Iterator[Dict[str, Any]]:
    """Потоково читает CSV в виде словарей."""
    with open(filepath_or_buffer, mode="r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=delimiter)
        for row in reader:
            yield dict(row)


def read_yaml_source(path_or_str: Union[str, Path], encoding: str = "utf-8") -> Iterator[Any]:
    """Читает YAML-источник (требуется PyYAML)."""
    try:
        import yaml
    except ImportError:
        raise ImportError("Для чтения YAML необходимо установить PyYAML: pip install pyyaml")

    target = Path(path_or_str) if isinstance(path_or_str, (str, Path)) and Path(path_or_str).is_file() else None
    if target:
        with open(target, mode="r", encoding=encoding) as f:
            data = yaml.safe_load(f)
    else:
        data = yaml.safe_load(str(path_or_str))

    if isinstance(data, list):
        yield from data
    else:
        yield data


def read_toml_source(path_or_str: Union[str, Path], encoding: str = "utf-8") -> Dict[str, Any]:
    """Читает TOML-источник (через tomllib из Python 3.11+ или tomli)."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            raise ImportError("Для чтения TOML в Python < 3.11 требуется tomli: pip install tomli")

    target = Path(path_or_str) if isinstance(path_or_str, (str, Path)) and Path(path_or_str).is_file() else None
    if target:
        with open(target, mode="rb") as f:
            return tomllib.load(f)
    return tomllib.loads(str(path_or_str))


def read_pandas_source(df: Any) -> Iterator[Dict[str, Any]]:
    """Лениво читает Pandas DataFrame построчно как словари."""
    for record in df.to_dict(orient="records"):
        yield record


def read_excel_source(
    filepath: Union[str, Path],
    sheet_name: Union[str, int] = 0,
) -> Iterator[Dict[str, Any]]:
    """Потоково читает строки таблицы Excel через openpyxl."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Для чтения Excel (.xlsx) необходимо установить openpyxl: pip install openpyxl")

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    sheet = wb[sheet_name] if isinstance(sheet_name, str) else wb.worksheets[sheet_name]

    rows = sheet.iter_rows(values_only=True)
    try:
        headers = [str(h) for h in next(rows)]
    except StopIteration:
        wb.close()
        return

    for row_values in rows:
        yield dict(zip(headers, row_values))

    wb.close()