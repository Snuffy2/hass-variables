"""Helpers for parsing and converting Variable values."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import copy
import datetime
import logging
from typing import Any, Never

import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


class _AttributePathTypeError(TypeError, ValueError):
    """Report incompatible containers while retaining the legacy ValueError API."""


def _parse_attribute_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    buffer = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            index += 1
            continue
        if char == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            closing = path.find("]", index)
            if closing == -1:
                raise ValueError(f"Invalid attribute path: {path}")
            index_str = path[index + 1 : closing]
            if not index_str.isdigit():
                raise ValueError(f"Invalid list index in attribute path: {path}")
            tokens.append(int(index_str))
            index = closing + 1
            continue
        buffer += char
        index += 1
    if buffer:
        tokens.append(buffer)
    return tokens


def looks_like_attribute_path(path: str) -> bool:
    """Return whether an attribute name uses supported nested-path syntax."""
    # Only treat bracket notation as nested paths (e.g., "test[a]")
    # Treat dots as literal attribute names for backward compatibility.
    if "[" in path:
        return True
    return False


def set_nested_attribute(target: MutableMapping[str, Any], path: str, value: Any) -> None:
    """Set a deeply nested mapping or list value from bracket-path notation."""
    tokens = _parse_attribute_path(path)
    if not tokens:
        raise ValueError("Attribute path cannot be empty")

    current: MutableMapping[str, Any] | list[Any] = target
    for idx, token in enumerate(tokens):
        is_last = idx == len(tokens) - 1
        if isinstance(token, str):
            if not isinstance(current, MutableMapping):
                raise _AttributePathTypeError(
                    f"Expected mapping while navigating attribute path: {path}"
                )
            if is_last:
                current[token] = copy.deepcopy(value)
            else:
                next_token = tokens[idx + 1]
                existing = current.get(token)
                if isinstance(next_token, int):
                    if not isinstance(existing, list):
                        existing = []
                elif not isinstance(existing, MutableMapping):
                    existing = {}
                current[token] = existing
                current = existing
        else:
            if not isinstance(current, list):
                raise _AttributePathTypeError(
                    f"Expected list while navigating attribute path: {path}"
                )
            list_next_token = tokens[idx + 1] if not is_last else None
            if is_last:
                while len(current) <= token:
                    current.append(None)
                current[token] = copy.deepcopy(value)
            else:
                next_container: list[Any] | MutableMapping[str, Any] = (
                    [] if isinstance(list_next_token, int) else {}
                )
                while len(current) <= token:
                    current.append(copy.deepcopy(next_container))
                if isinstance(list_next_token, int):
                    if not isinstance(current[token], list):
                        current[token] = []
                elif not isinstance(current[token], MutableMapping):
                    current[token] = {}
                current = current[token]


def merge_attribute_dict(
    existing: Mapping[str, Any] | None, updates: Mapping[str, Any]
) -> dict[str, Any]:
    """Deep-copy and merge attributes, resolving bracket-path keys."""
    merged = copy.deepcopy(dict(existing)) if existing is not None else {}
    for attr, value in updates.items():
        if isinstance(attr, str) and looks_like_attribute_path(attr):
            set_nested_attribute(merged, attr, value)
        else:
            merged[attr] = copy.deepcopy(value)
    return merged


def to_num(s: str) -> int | float | None:
    """Convert a string to an integer or float when possible."""
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def _raise_conversion_error(source: str, dest_type: str, value: object) -> Never:
    """Raise a consistent conversion error after recording debug context."""
    _LOGGER.debug("Cannot convert %s to %s: %s, returning None", source, dest_type, value)
    raise ValueError(f"Cannot convert {source} to {dest_type}: {value}")


def _normalize_datetime(value: datetime.datetime) -> datetime.datetime:
    """Attach UTC to naive datetime values while retaining aware values."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=dt_util.UTC)
    return value


def _string_to_type(
    value: str, dest_type: str | None
) -> str | int | float | datetime.date | datetime.datetime:
    """Convert a string to the requested variable value type."""
    if dest_type is None or dest_type == "string":
        return value
    if dest_type == "date":
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            _raise_conversion_error("string", dest_type, value)
    if dest_type == "datetime":
        try:
            return _normalize_datetime(datetime.datetime.fromisoformat(value))
        except ValueError:
            _raise_conversion_error("string", dest_type, value)
    if dest_type == "number":
        if (number := to_num(value)) is not None:
            return number
        _raise_conversion_error("string", dest_type, value)
    raise ValueError(f"Invalid dest_type: {dest_type}")


def _number_to_type(
    value: float, dest_type: str | None
) -> str | float | datetime.date | datetime.datetime:
    """Convert a numeric value to the requested variable value type."""
    if dest_type is None or dest_type == "string":
        return str(value)
    if dest_type == "date":
        try:
            return datetime.date.fromisoformat(str(value))
        except ValueError:
            _raise_conversion_error("number", dest_type, value)
    if dest_type == "datetime":
        try:
            return _normalize_datetime(datetime.datetime.fromisoformat(str(value)))
        except ValueError:
            _raise_conversion_error("number", dest_type, value)
    if dest_type == "number":
        return value
    raise ValueError(f"Invalid dest_type: {dest_type}")


def _date_to_type(
    value: datetime.date, dest_type: str | None
) -> str | float | datetime.date | datetime.datetime:
    """Convert a date to the requested variable value type."""
    if dest_type is None or dest_type == "string":
        return value.isoformat()
    if dest_type == "date":
        return value
    combined = datetime.datetime.combine(value, datetime.time.min)
    if dest_type == "datetime":
        return combined
    if dest_type == "number":
        return combined.timestamp()
    raise ValueError(f"Invalid dest_type: {dest_type}")


def _datetime_to_type(
    value: datetime.datetime, dest_type: str | None
) -> str | float | datetime.date | datetime.datetime:
    """Convert a datetime to the requested variable value type."""
    if dest_type is None or dest_type == "string":
        return value.isoformat()
    if dest_type == "date":
        return value.date()
    if dest_type == "datetime":
        return value
    if dest_type == "number":
        return value.timestamp()
    raise ValueError(f"Invalid dest_type: {dest_type}")


def value_to_type(
    init_val: Any, dest_type: str | None
) -> str | int | float | datetime.date | datetime.datetime | None:
    """Convert a variable value to its configured destination type."""
    if init_val is None or (
        isinstance(init_val, str) and init_val.lower() in ["", "none", "unknown", "unavailable"]
    ):
        _LOGGER.debug("[value_to_type] return value: %s, returning None", init_val)
        return None

    # Convert Wrapper types and other non-native types to strings
    # This handles HA 2026.3.4+ template engine's Wrapper type from | tojson
    if not isinstance(init_val, (str, int, float, datetime.date, datetime.datetime)):
        init_val = str(init_val)

    if isinstance(init_val, str):
        return _string_to_type(init_val, dest_type)
    if isinstance(init_val, (int, float)):
        return _number_to_type(init_val, dest_type)
    if type(init_val) is datetime.date:
        return _date_to_type(init_val, dest_type)
    if type(init_val) is datetime.datetime:
        return _datetime_to_type(init_val, dest_type)
    raise ValueError(f"Invalid initial type: {type(init_val)}")
