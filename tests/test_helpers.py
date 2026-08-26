"""Tests for public Variable integration helper behavior."""

from __future__ import annotations

from collections.abc import MutableMapping
import copy
import datetime

import pytest

from custom_components.variable.helpers import (
    merge_attribute_dict,
    set_nested_attribute,
    to_num,
    value_to_type,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("42", 42, id="integer"),
        pytest.param("4.25", 4.25, id="float"),
        pytest.param("not-a-number", None, id="invalid"),
    ],
)
def test_to_num(value: str, expected: float | None) -> None:
    """Parse numeric strings without raising for invalid input.

    Args:
        value (str): String to parse.
        expected (float | None): Parsed numeric value, or None for invalid input.
    """
    assert to_num(value) == expected


def test_set_nested_attribute_creates_and_expands_containers() -> None:
    """Create nested mappings and expand list indices with placeholders."""
    target: MutableMapping[str, object] = {}

    set_nested_attribute(target, "rooms[2].sensors[1]", "online")

    assert target == {
        "rooms": [{}, {}, {"sensors": [None, "online"]}],
    }


@pytest.mark.parametrize(
    ("initial", "path", "expected"),
    [
        pytest.param(
            {"node": "old"},
            "node[0].value",
            {"node": [{"value": "new"}]},
            id="scalar-replaced-with-list",
        ),
        pytest.param(
            {"node": [{"value": "old"}]},
            "node[0][1]",
            {"node": [[None, "new"]]},
            id="mapping-replaced-with-list",
        ),
        pytest.param(
            {"node": ["old"]},
            "node[0].value",
            {"node": [{"value": "new"}]},
            id="scalar-list-item-replaced-with-mapping",
        ),
        pytest.param(
            {"node": "scalar"},
            "node.child",
            {"node": {"child": "new"}},
            id="scalar-replaced-with-mapping",
        ),
        pytest.param(
            {"node": [["keep"]]},
            "node[0][1]",
            {"node": [["keep", "new"]]},
            id="existing-nested-list-reused",
        ),
    ],
)
def test_set_nested_attribute_replaces_incompatible_containers(
    initial: MutableMapping[str, object],
    path: str,
    expected: MutableMapping[str, object],
) -> None:
    """Replace incompatible intermediate values for the requested path.

    Args:
        initial (MutableMapping[str, object]): Mapping containing an incompatible intermediate value.
        path (str): Bracket path to update.
        expected (MutableMapping[str, object]): Mapping expected after the update.
    """
    set_nested_attribute(initial, path, "new")

    assert initial == expected


def test_set_nested_attribute_deep_copies_assigned_value() -> None:
    """Keep assigned nested values independent from caller mutation."""
    target: MutableMapping[str, object] = {}
    value = {"labels": ["original"]}

    set_nested_attribute(target, "items[0]", value)
    value["labels"].append("changed")

    assert target == {"items": [{"labels": ["original"]}]}


@pytest.mark.parametrize(
    ("target", "path", "message"),
    [
        pytest.param({}, "", "Attribute path cannot be empty", id="empty-path"),
        pytest.param(
            {},
            "items[0",
            "Invalid attribute path",
            id="unmatched-bracket",
        ),
        pytest.param(
            {},
            "items[first]",
            "Invalid list index",
            id="nonnumeric-index",
        ),
        pytest.param(
            [],
            "items",
            "Expected mapping",
            id="wrong-root-container",
        ),
        pytest.param(
            {},
            "[0]",
            "Expected list",
            id="list-index-on-mapping-root",
        ),
    ],
)
def test_set_nested_attribute_rejects_invalid_paths(
    target: object, path: str, message: str
) -> None:
    """Raise ValueError for malformed paths and incompatible roots.

    Args:
        target (object): Root container supplied by the caller.
        path (str): Invalid path to apply.
        message (str): Expected error message fragment.
    """
    with pytest.raises(ValueError, match=message):
        set_nested_attribute(target, path, "value")  # type: ignore[arg-type]


def test_merge_attribute_dict_applies_literal_and_nested_updates() -> None:
    """Merge direct, dot-literal, and bracket-path keys."""
    existing: MutableMapping[str, object] = {
        "kept": True,
        "items": [{"name": "before"}],
    }
    updates: MutableMapping[str, object] = {
        "direct": {"value": 1},
        "literal.name": "unchanged",
        "items[0].name": "after",
    }

    merged = merge_attribute_dict(existing, updates)

    assert merged == {
        "kept": True,
        "items": [{"name": "after"}],
        "direct": {"value": 1},
        "literal.name": "unchanged",
    }


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param(None, id="no-existing-attributes"),
        pytest.param({"kept": ["original"]}, id="existing-attributes"),
    ],
)
def test_merge_attribute_dict_deep_copies_without_mutating_inputs(
    existing: MutableMapping[str, object] | None,
) -> None:
    """Return an isolated merge without mutating either input.

    Args:
        existing (MutableMapping[str, object] | None): Existing attributes, or None for a new mapping.
    """
    updates: MutableMapping[str, object] = {"added": ["original"]}
    existing_snapshot = copy.deepcopy(existing)

    merged = merge_attribute_dict(existing, updates)
    added = merged["added"]
    assert isinstance(added, list)
    added.append("changed")
    if existing is not None:
        kept = merged["kept"]
        assert isinstance(kept, list)
        kept.append("changed")

    assert updates == {"added": ["original"]}
    assert existing == existing_snapshot


class StringWrapper:
    """Represent a non-native template wrapper convertible to a string."""

    def __str__(self) -> str:
        """Return the wrapped text.

        Returns:
            str: Text exposed by the wrapper.
        """
        return "wrapped"


class DateSubclass(datetime.date):
    """Represent a concrete date subclass accepted by helper conversion."""


class DatetimeSubclass(datetime.datetime):
    """Represent a concrete datetime subclass accepted by helper conversion."""


@pytest.mark.parametrize(
    "initial",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty-string"),
        pytest.param("NONE", id="none-string"),
        pytest.param("Unknown", id="unknown-string"),
        pytest.param("unavailable", id="unavailable-string"),
    ],
)
def test_value_to_type_returns_none_for_null_like_values(initial: str | None) -> None:
    """Normalize null-like values before destination conversion.

    Args:
        initial (str | None): Null-like value to normalize.
    """
    assert value_to_type(initial, "number") is None


def test_value_to_type_converts_wrapper_to_string() -> None:
    """Convert non-native wrapper values through their string representation."""
    assert value_to_type(StringWrapper(), "string") == "wrapped"


@pytest.mark.parametrize(
    ("initial", "destination", "expected"),
    [
        pytest.param("text", None, "text", id="default-string"),
        pytest.param("text", "string", "text", id="explicit-string"),
        pytest.param(
            "2026-07-24",
            "date",
            datetime.date(2026, 7, 24),
            id="date",
        ),
        pytest.param(
            "2026-07-24T12:30:00",
            "datetime",
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
            id="naive-datetime-assumes-utc",
        ),
        pytest.param(
            "2026-07-24T12:30:00+02:00",
            "datetime",
            datetime.datetime(
                2026,
                7,
                24,
                12,
                30,
                tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
            ),
            id="aware-datetime-preserved",
        ),
        pytest.param("42", "number", 42, id="integer"),
        pytest.param("4.25", "number", 4.25, id="float"),
        pytest.param("'87'", "number", 87, id="single-quoted-integer"),
        pytest.param('"4.25"', "number", 4.25, id="double-quoted-float"),
        pytest.param("'87'", None, "87", id="single-quoted-default-string"),
        pytest.param("'87'", "string", "87", id="single-quoted-explicit-string"),
        pytest.param("\u201887\u2019", "number", 87, id="typographic-single-quoted-integer"),
        pytest.param("\u201c4.25\u201d", "number", 4.25, id="typographic-double-quoted-float"),
        pytest.param("'2026-07-24'", "date", datetime.date(2026, 7, 24), id="single-quoted-date"),
    ],
)
def test_value_to_type_converts_strings(
    initial: str,
    destination: str | None,
    expected: str | int | float | datetime.date | datetime.datetime,
) -> None:
    """Convert valid strings to the requested public destination type.

    Args:
        initial (str): String value to convert.
        destination (str | None): Requested destination type, or None for the default.
        expected (str | int | float | datetime.date | datetime.datetime): Converted value.
    """
    assert value_to_type(initial, destination) == expected


@pytest.mark.parametrize(
    ("initial", "destination", "expected"),
    [
        pytest.param("'hello'", "string", "hello", id="quoted-text"),
        pytest.param("'87", "string", "'87", id="unmatched-opening-quote"),
        pytest.param("''", "string", None, id="quoted-empty"),
        pytest.param("'none'", "number", None, id="quoted-none"),
        pytest.param("'unknown'", None, None, id="quoted-unknown"),
    ],
)
def test_value_to_type_unwraps_wrapping_quotes(
    initial: str,
    destination: str | None,
    expected: str | None,
) -> None:
    """Strip one matching quote layer before converting or treating as empty.

    Args:
        initial (str): Quoted or partially quoted string value.
        destination (str | None): Requested destination type, or None for the default.
        expected (str | None): Converted value after quote unwrapping.
    """
    assert value_to_type(initial, destination) == expected


@pytest.mark.parametrize(
    ("initial", "destination", "message"),
    [
        pytest.param("invalid", "date", "Cannot convert string to date", id="invalid-date"),
        pytest.param(
            "invalid",
            "datetime",
            "Cannot convert string to datetime",
            id="invalid-datetime",
        ),
        pytest.param(
            "invalid",
            "number",
            "Cannot convert string to number",
            id="invalid-number",
        ),
        pytest.param(
            "87'",
            "number",
            "Cannot convert string to number",
            id="trailing-quote-only",
        ),
        pytest.param("value", "boolean", "Invalid dest_type", id="invalid-destination"),
    ],
)
def test_value_to_type_rejects_invalid_string_conversions(
    initial: str, destination: str, message: str
) -> None:
    """Reject unsupported or malformed string conversions.

    Args:
        initial (str): String value that cannot satisfy the conversion.
        destination (str): Requested destination type.
        message (str): Expected error message fragment.
    """
    with pytest.raises(ValueError, match=message):
        value_to_type(initial, destination)


@pytest.mark.parametrize(
    ("initial", "destination", "expected"),
    [
        pytest.param(42, None, "42", id="default-string"),
        pytest.param(4.25, "string", "4.25", id="explicit-string"),
        pytest.param(
            20260724,
            "date",
            datetime.date(2026, 7, 24),
            id="date",
        ),
        pytest.param(
            20260724,
            "datetime",
            datetime.datetime(2026, 7, 24, tzinfo=datetime.UTC),
            id="datetime",
        ),
        pytest.param(42, "number", 42, id="integer-number"),
        pytest.param(4.25, "number", 4.25, id="float-number"),
    ],
)
def test_value_to_type_converts_numbers(
    initial: float,
    destination: str | None,
    expected: str | float | datetime.date | datetime.datetime,
) -> None:
    """Convert numeric input to supported destination types.

    Args:
        initial (float): Numeric value to convert.
        destination (str | None): Requested destination type, or None for the default.
        expected (str | float | datetime.date | datetime.datetime): Converted value.
    """
    assert value_to_type(initial, destination) == expected


@pytest.mark.parametrize(
    ("destination", "message"),
    [
        pytest.param("date", "Cannot convert number to date", id="invalid-date"),
        pytest.param(
            "datetime",
            "Cannot convert number to datetime",
            id="invalid-datetime",
        ),
        pytest.param("boolean", "Invalid dest_type", id="invalid-destination"),
    ],
)
def test_value_to_type_rejects_invalid_numeric_conversions(destination: str, message: str) -> None:
    """Reject malformed or unsupported numeric conversions.

    Args:
        destination (str): Requested destination type.
        message (str): Expected error message fragment.
    """
    with pytest.raises(ValueError, match=message):
        value_to_type(1, destination)


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        pytest.param(None, "2026-07-24", id="default-string"),
        pytest.param("string", "2026-07-24", id="explicit-string"),
        pytest.param("date", datetime.date(2026, 7, 24), id="date"),
        pytest.param(
            "datetime",
            datetime.datetime(2026, 7, 24, tzinfo=datetime.UTC),
            id="datetime",
        ),
        pytest.param(
            "number",
            datetime.datetime(2026, 7, 24, tzinfo=datetime.UTC).timestamp(),
            id="number",
        ),
    ],
)
def test_value_to_type_converts_dates(
    destination: str | None,
    expected: str | float | datetime.date | datetime.datetime,
) -> None:
    """Convert date input to supported destination types.

    Args:
        destination (str | None): Requested destination type, or None for the default.
        expected (str | float | datetime.date | datetime.datetime): Converted value.
    """
    assert value_to_type(datetime.date(2026, 7, 24), destination) == expected


def test_value_to_type_converts_date_subclass() -> None:
    """Convert a date subclass using the date conversion path."""
    initial = DateSubclass(2026, 7, 24)

    assert value_to_type(initial, "string") == "2026-07-24"


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        pytest.param(None, "2026-07-24T12:30:00+00:00", id="default-string"),
        pytest.param("string", "2026-07-24T12:30:00+00:00", id="explicit-string"),
        pytest.param("date", datetime.date(2026, 7, 24), id="date"),
        pytest.param(
            "datetime",
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
            id="datetime",
        ),
        pytest.param(
            "number",
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC).timestamp(),
            id="number",
        ),
    ],
)
def test_value_to_type_converts_datetimes(
    destination: str | None,
    expected: str | float | datetime.date | datetime.datetime,
) -> None:
    """Convert an aware datetime to supported destination types.

    Args:
        destination (str | None): Requested destination type, or None for the default.
        expected (str | float | datetime.date | datetime.datetime): Converted value.
    """
    initial = datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC)

    assert value_to_type(initial, destination) == expected


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        pytest.param("date", datetime.date(2026, 7, 24), id="date"),
        pytest.param(
            "datetime",
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
            id="datetime-assumes-utc",
        ),
        pytest.param(
            "number",
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC).timestamp(),
            id="number-uses-utc",
        ),
    ],
)
def test_value_to_type_normalizes_naive_datetimes(
    destination: str,
    expected: float | datetime.date | datetime.datetime,
) -> None:
    """Normalize naive datetime input before temporal and numeric conversion.

    Args:
        destination (str): Requested destination type.
        expected (float | datetime.date | datetime.datetime): UTC-normalized value.
    """
    initial = datetime.datetime.fromisoformat("2026-07-24T12:30:00")

    assert value_to_type(initial, destination) == expected


def test_value_to_type_converts_datetime_subclass() -> None:
    """Convert a datetime subclass using the datetime conversion path."""
    initial = DatetimeSubclass(2026, 7, 24, 12, 30, tzinfo=datetime.UTC)

    assert value_to_type(initial, "date") == datetime.date(2026, 7, 24)
    assert value_to_type(initial, "datetime") is initial


@pytest.mark.parametrize(
    "initial",
    [
        pytest.param(datetime.date(2026, 7, 24), id="date"),
        pytest.param(
            datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
            id="aware-datetime",
        ),
    ],
)
def test_value_to_type_rejects_invalid_temporal_destination(
    initial: datetime.date | datetime.datetime,
) -> None:
    """Reject an unsupported destination for temporal input.

    Args:
        initial (datetime.date | datetime.datetime): Date or timezone-aware datetime input.
    """
    with pytest.raises(ValueError, match="Invalid dest_type"):
        value_to_type(initial, "boolean")
