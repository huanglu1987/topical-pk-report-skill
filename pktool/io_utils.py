from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_parent(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def read_json(path: str | Path, default: Any | None = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, data: Any) -> None:
    ensure_parent(path)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(data), handle, ensure_ascii=False, indent=2, allow_nan=False)


def _json_safe(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: _json_safe(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_json_safe(value) for value in data]
    if isinstance(data, tuple):
        return [_json_safe(value) for value in data]
    if isinstance(data, float) and (math.isnan(data) or math.isinf(data)):
        return None
    return data


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    text = str(value).strip()
    if text == "" or text.lower() in {"na", "nan", "none", "null", "/"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def load_compound_profile(path: str | Path) -> dict[str, Any]:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"compound profile is empty: {path}")
    row = df.iloc[0].to_dict()
    return {normalize_key(str(k)): v for k, v in row.items()}


def load_reference_pk(path: str | Path) -> dict[str, Any]:
    df = pd.read_csv(path)
    if df.empty:
        return {}
    lower_columns = {normalize_key(c): c for c in df.columns}
    if "parameter" in lower_columns and "value" in lower_columns:
        result: dict[str, Any] = {}
        for _, row in df.iterrows():
            key = normalize_key(str(row[lower_columns["parameter"]]))
            result[key] = row[lower_columns["value"]]
        return result
    row = df.iloc[0].to_dict()
    return {normalize_key(str(k)): v for k, v in row.items()}


def get_numeric(mapping: dict[str, Any], keys: list[str], default: float | None = None) -> float | None:
    for key in keys:
        if key in mapping:
            value = to_float(mapping[key])
            if value is not None:
                return value
    return default


def get_range(mapping: dict[str, Any], key: str, default: tuple[float, float]) -> tuple[float, float]:
    value = mapping.get(key)
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low = to_float(value[0])
        high = to_float(value[1])
    elif isinstance(value, str) and "," in value:
        parts = value.split(",", 1)
        low = to_float(parts[0])
        high = to_float(parts[1])
    else:
        single = to_float(value)
        low = single
        high = single
    if low is None or high is None:
        return default
    if low > high:
        low, high = high, low
    return float(low), float(high)


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
