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
    """Tokenize an attribute path into mapping keys and list indexes.

    Dot-delimited path components become string tokens, while numeric components
    enclosed in brackets become integer tokens.

    Args:
        path (str): Attribute path to tokenize.

    Returns:
        list[str | int]: The ordered mapping-key and list-index tokens from the path.

    Raises:
        ValueError: If a bracket is unclosed or contains a non-numeric index.
    """
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


def set_nested_attribute(target: MutableMapping[str, Any], path: str, value: Any) -> None:
    """Set a deeply nested mapping or list value from bracket-path notation.

    Args:
        target (MutableMapping[str, Any]): Mutable mapping to update in place.
        path (str): Dot- and bracket-delimited path to the target value.
        value (Any): Value to deep-copy into the target path.

    Raises:
        ValueError: If the path is empty or has invalid bracket notation.
        _AttributePathTypeError: If an existing container conflicts with the path.
    """
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
    """Deep-copy and merge attributes, resolving bracket-path keys.

    Args:
        existing (Mapping[str, Any] | None): Existing attributes to preserve, if any.
        updates (Mapping[str, Any]): New attributes to merge into the result.

    Returns:
        dict[str, Any]: A deep-copied attribute mapping containing both inputs.
    """
    merged = copy.deepcopy(dict(existing)) if existing is not None else {}
    for attr, value in updates.items():
        if isinstance(attr, str) and "[" in attr:
            set_nested_attribute(merged, attr, value)
        else:
            merged[attr] = copy.deepcopy(value)
    return merged


def to_num(s: str) -> int | float | None:
    """Convert a string to an integer or float when possible.

    Args:
        s (str): String representation of a numeric value.

    Returns:
        int | float | None: The parsed integer or float, or ``None`` when the string is not numeric.
    """
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def _raise_conversion_error(source: str, dest_type: str, value: object) -> Never:
    """Raise a consistent conversion error after recording debug context.

    Args:
        source (str): Source value category that could not be converted.
        dest_type (str): Requested Variable value type.
        value (object): Value that failed conversion.

    Raises:
        ValueError: Always, with the conversion context.

    Returns:
        Never: Does not return; raises a ValueError naming the source, destination, and value.
    """
    _LOGGER.debug("Cannot convert %s to %s: %s, returning None", source, dest_type, value)
    raise ValueError(f"Cannot convert {source} to {dest_type}: {value}")


def _normalize_datetime(value: datetime.datetime) -> datetime.datetime:
    """Attach UTC to naive datetime values while retaining aware values.

    Args:
        value (datetime.datetime): Datetime value to normalize.

    Returns:
        datetime.datetime: The original aware datetime or a UTC-aware replacement for a naive one.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=dt_util.UTC)
    return value


def _string_to_type(
    value: str, dest_type: str | None
) -> str | int | float | datetime.date | datetime.datetime:
    """Convert a string to the requested variable value type.

    Args:
        value (str): String value to convert.
        dest_type (str | None): Requested Variable value type.

    Returns:
        str | int | float | datetime.date | datetime.datetime: The value converted
            to the requested type.

    Raises:
        ValueError: If the destination type is invalid or conversion fails.
    """
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
    """Convert a numeric value to the requested variable value type.

    Args:
        value (float): Numeric value to convert.
        dest_type (str | None): Requested Variable value type.

    Returns:
        str | float | datetime.date | datetime.datetime: The value converted to the requested type.

    Raises:
        ValueError: If the destination type is invalid or conversion fails.
    """
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
    """Convert a date to the requested variable value type.

    Args:
        value (datetime.date): Date value to convert.
        dest_type (str | None): Requested Variable value type.

    Returns:
        str | float | datetime.date | datetime.datetime: The value converted to the requested type.

    Raises:
        ValueError: If the destination type is invalid.
    """
    if dest_type is None or dest_type == "string":
        return value.isoformat()
    if dest_type == "date":
        return value
    combined = _normalize_datetime(datetime.datetime.combine(value, datetime.time.min))
    if dest_type == "datetime":
        return combined
    if dest_type == "number":
        return combined.timestamp()
    raise ValueError(f"Invalid dest_type: {dest_type}")


def _datetime_to_type(
    value: datetime.datetime, dest_type: str | None
) -> str | float | datetime.date | datetime.datetime:
    """Convert a datetime to the requested variable value type.

    Args:
        value (datetime.datetime): Datetime value to convert.
        dest_type (str | None): Requested Variable value type.

    Returns:
        str | float | datetime.date | datetime.datetime: The value converted to the requested type.

    Raises:
        ValueError: If the destination type is invalid.
    """
    if dest_type is None or dest_type == "string":
        return value.isoformat()
    value = _normalize_datetime(value)
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
    """Convert a variable value to its configured destination type.

    Args:
        init_val (Any): Initial value supplied by YAML, a service, or a template.
        dest_type (str | None): Requested Variable value type.

    Returns:
        str | int | float | datetime.date | datetime.datetime | None: The converted
            value, or ``None`` for an empty or unavailable input.

    Raises:
        ValueError: If the input or destination type is invalid.
    """
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
    if isinstance(init_val, datetime.datetime):
        return _datetime_to_type(init_val, dest_type)
    if isinstance(init_val, datetime.date):
        return _date_to_type(init_val, dest_type)
    raise ValueError(f"Invalid initial type: {type(init_val)}")
