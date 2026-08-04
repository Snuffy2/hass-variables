"""Shared type aliases for Variable integration tests."""

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry

ConfigEntryFactory = Callable[[Mapping[str, Any]], ConfigEntry]
