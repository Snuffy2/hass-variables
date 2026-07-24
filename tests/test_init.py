"""End-to-end setup orchestration tests for the Variable integration."""

from collections.abc import Callable, Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    SERVICE_RELOAD,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import pytest

from custom_components.variable.const import (
    CONF_ENTITY_PLATFORM,
    CONF_VALUE,
    CONF_VARIABLE_ID,
    CONF_YAML_PRESENT,
    CONF_YAML_VARIABLE,
    DOMAIN,
)

ConfigEntryFactory = Callable[[Mapping[str, Any]], ConfigEntry]


async def test_yaml_setup_and_reload_manage_config_entries(
    hass: HomeAssistant,
) -> None:
    """Create, update, and remove YAML variables through Home Assistant APIs.

    Args:
        hass: Home Assistant instance that hosts the integration.
    """
    initial_config = {
        DOMAIN: {
            "yaml_temperature": {
                CONF_VALUE: 20,
                "attributes": {"source": "initial"},
            },
            "yaml_removed": {
                CONF_VALUE: "present",
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    entries = {
        entry.data[CONF_VARIABLE_ID]: entry for entry in hass.config_entries.async_entries(DOMAIN)
    }
    temperature_entry = entries["yaml_temperature"]
    removed_entry = entries["yaml_removed"]
    assert temperature_entry.data[CONF_YAML_VARIABLE] is True
    assert temperature_entry.data[CONF_ENTITY_PLATFORM] == Platform.SENSOR
    initial_state = hass.states.get("sensor.yaml_temperature")
    assert initial_state is not None
    assert initial_state.state == "20"
    assert initial_state.attributes["source"] == "initial"
    removed_state = hass.states.get("sensor.yaml_removed")
    assert removed_state is not None
    removed_registry_entry = er.async_get(hass).async_get("sensor.yaml_removed")
    assert removed_registry_entry is not None
    assert removed_registry_entry.config_entry_id == removed_entry.entry_id

    reloaded_config = {
        DOMAIN: {
            "yaml_temperature": {
                CONF_VALUE: 24,
                "attributes": {"source": "reload"},
            }
        }
    }
    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value=reloaded_config),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    current_entry = hass.config_entries.async_get_entry(temperature_entry.entry_id)
    assert current_entry is not None
    assert current_entry.data[CONF_VALUE] == 24
    assert current_entry.data[CONF_YAML_VARIABLE] is True
    assert CONF_YAML_PRESENT not in current_entry.data
    reloaded_state = hass.states.get("sensor.yaml_temperature")
    assert reloaded_state is not None
    assert reloaded_state.state == "24"
    assert reloaded_state.attributes["source"] == "reload"
    assert hass.config_entries.async_get_entry(removed_entry.entry_id) is None
    assert hass.states.get("sensor.yaml_removed") is None
    assert er.async_get(hass).async_get("sensor.yaml_removed") is None


@pytest.mark.parametrize(
    ("data", "entity_id", "expected_state", "expected_attributes"),
    [
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.SENSOR,
                CONF_VARIABLE_ID: "workflow_sensor",
                CONF_VALUE: "ready",
                "value_type": "string",
            },
            "sensor.workflow_sensor",
            "ready",
            {"marker": "sensor"},
            id="sensor",
        ),
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
                CONF_VARIABLE_ID: "workflow_switch",
                CONF_VALUE: "true",
            },
            "binary_sensor.workflow_switch",
            STATE_ON,
            {"marker": "binary"},
            id="binary-sensor",
        ),
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
                CONF_VARIABLE_ID: "workflow_tracker",
                ATTR_LATITUDE: 40.0,
                ATTR_LONGITUDE: -75.0,
                ATTR_GPS_ACCURACY: 15,
                ATTR_BATTERY_LEVEL: 90,
            },
            "device_tracker.workflow_tracker",
            "not_home",
            {"latitude": 40.0, "longitude": -75.0, "marker": "tracker"},
            id="device-tracker",
        ),
    ],
)
async def test_setup_entry_creates_platform_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    data: dict[str, Any],
    entity_id: str,
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Load a config entry and expose its entity through Home Assistant state.

    Args:
        hass: Home Assistant instance that hosts the integration.
        config_entry_factory: Factory that creates the platform config entry.
        data: Platform-specific config-entry data to load.
        entity_id: Expected entity identifier after setup.
        expected_state: Expected state value for the created entity.
        expected_attributes: Expected attributes for the created entity.
    """
    marker = expected_attributes["marker"]
    entry_data = {
        **data,
        CONF_YAML_VARIABLE: False,
        "restore": False,
        "force_update": False,
        "attributes": {"marker": marker},
    }
    entry = config_entry_factory(entry_data)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    for attribute, value in expected_attributes.items():
        assert state.attributes[attribute] == value

    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.config_entry_id == entry.entry_id


async def test_unload_entry_removes_entity(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Unload a platform entry and remove both state and registry records.

    Args:
        hass: Home Assistant instance that hosts the integration.
        sensor_entry: Sensor config entry to set up and unload.
    """
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_temperature") is not None

    assert await hass.config_entries.async_unload(sensor_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.office_temperature") is None
    assert er.async_get(hass).async_get("sensor.office_temperature") is None
