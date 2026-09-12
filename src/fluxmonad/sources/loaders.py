import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Union, cast


def read_json_source(
    path_or_str: Union[str, Path],
    lines: bool = False,
    encoding: str = "utf-8",
) -> Iterator[Any]:
    """Reads a JSON file/string (or JSON Lines when lines=True)."""
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
        # Parsing raw string
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
    """Streams rows from a CSV file as dictionaries."""
    with open(filepath_or_buffer, mode="r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=delimiter)
        for row in reader:
            yield dict(row)


def read_yaml_source(path_or_str: Union[str, Path], encoding: str = "utf-8") -> Iterator[Any]:
    """Reads a YAML source into a stream (requires PyYAML)."""
    try:
        import yaml
    except ImportError:
        raise ImportError("Reading YAML requires PyYAML: pip install pyyaml")

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
    """Reads a TOML source (via tomllib on Python 3.11+ or tomli)."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib
        except ImportError:
            raise ImportError("Reading TOML on Python < 3.11 requires tomli: pip install tomli")

    target = Path(path_or_str) if isinstance(path_or_str, (str, Path)) and Path(path_or_str).is_file() else None
    if target:
        with open(target, mode="rb") as f:
            return cast(Dict[str, Any], tomllib.load(f))
    return cast(Dict[str, Any], tomllib.loads(str(path_or_str)))


def read_pandas_source(df: Any) -> Iterator[Dict[str, Any]]:
    """Lazily reads a Pandas DataFrame row by row as dictionaries."""
    for record in df.to_dict(orient="records"):
        yield record


def read_excel_source(
    filepath: Union[str, Path],
    sheet_name: Union[str, int] = 0,
) -> Iterator[Dict[str, Any]]:
    """Streams rows from an Excel spreadsheet (.xlsx) via openpyxl."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Reading Excel (.xlsx) requires openpyxl: pip install openpyxl")

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