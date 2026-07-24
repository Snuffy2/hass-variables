"""Shared pytest fixtures for the Variable integration."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components
from custom_components.variable.const import (
    CONF_ENTITY_PLATFORM,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
)

ConfigEntryFactory = Callable[[Mapping[str, Any]], ConfigEntry]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enable loading custom integrations in every test."""
    monkeypatch.setattr(
        custom_components,
        "__path__",
        [str(Path(__file__).parents[1] / "custom_components")],
    )


@pytest.fixture
def config_entry_factory(hass: HomeAssistant) -> ConfigEntryFactory:
    """Return a factory that adds a Variable config entry to Home Assistant."""

    def _create(data: Mapping[str, Any]) -> ConfigEntry:
        """Create and register a Variable config entry from the supplied data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=str(data.get(CONF_VARIABLE_ID, data.get("name", "Variable"))),
            data=dict(data),
        )
        entry.add_to_hass(hass)
        return entry

    return _create


@pytest.fixture
def sensor_entry(config_entry_factory: ConfigEntryFactory) -> ConfigEntry:
    """Create a representative sensor config entry."""
    return config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "office_temperature",
            CONF_YAML_VARIABLE: False,
            "name": "Office Temperature",
            "restore": False,
            "force_update": False,
            "value": 21.5,
            "value_type": "number",
            "attributes": {"source": "test"},
        }
    )
