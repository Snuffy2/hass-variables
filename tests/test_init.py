"""End-to-end config-entry setup tests for the Variable integration."""

from collections.abc import Callable, Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.device_tracker.const import ATTR_LOCATION_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_CONFIGURATION_URL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    CONF_DEVICE,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import pytest

from custom_components.variable.const import (
    ATTR_ATTRIBUTES,
    ATTR_REPLACE_ATTRIBUTES,
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_EXCLUDE_FROM_RECORDER,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_VALUE,
    CONF_VARIABLE_ID,
    CONF_YAML_PRESENT,
    CONF_YAML_VARIABLE,
    DOMAIN,
    SERVICE_UPDATE_SENSOR,
)

ConfigEntryFactory = Callable[[Mapping[str, Any]], ConfigEntry]


async def test_yaml_setup_and_reload_manage_config_entries(
    hass: HomeAssistant,
) -> None:
    """Create, update, and remove YAML variables through Home Assistant APIs."""
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


async def test_yaml_entry_aborts_options_flow(hass: HomeAssistant) -> None:
    """Reject options for a variable managed through YAML."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"yaml_managed": {CONF_VALUE: "managed"}}},
    )
    await hass.async_block_till_done()
    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == "yaml_managed"
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "yaml_variable"


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
    """Load a config entry and expose its entity through Home Assistant state."""
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


async def test_setup_device_entry_creates_registry_device(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Load a device config entry and register its metadata."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: CONF_DEVICE,
            CONF_NAME: "Virtual Hub",
            CONF_YAML_VARIABLE: False,
            ATTR_MANUFACTURER: "Variables",
            ATTR_CONFIGURATION_URL: "https://example.com/device",
        }
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "Virtual Hub"
    assert device.manufacturer == "Variables"
    assert str(device.configuration_url) == "https://example.com/device"


async def test_unload_entry_removes_entity(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Unload a platform entry and remove both state and registry records."""
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_temperature") is not None

    assert await hass.config_entries.async_unload(sensor_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.office_temperature") is None
    assert er.async_get(hass).async_get("sensor.office_temperature") is None


async def test_options_flow_changes_loaded_sensor_value(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Change a live entity through the options workflow and its entity service."""
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(sensor_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["change_sensor_value", "sensor_options"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "change_sensor_value"},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_VALUE: "24.25", "attributes": {"source": "options"}},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "value_changed"
    state = hass.states.get("sensor.office_temperature")
    assert state is not None
    assert state.state == "24.25"
    assert state.attributes["source"] == "options"


async def test_sensor_options_flow_updates_entry_and_live_entity(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Persist both sensor option pages and reload the live entity."""
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(sensor_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "sensor_options"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_options"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "device_class": "None",
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: True,
            CONF_EXCLUDE_FROM_RECORDER: True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_options_page_2"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_VALUE: "26.5",
            CONF_ATTRIBUTES: {"source": "sensor-options"},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert sensor_entry.data[CONF_VALUE] == "26.5"
    assert sensor_entry.data[CONF_FORCE_UPDATE] is True
    assert sensor_entry.data[CONF_EXCLUDE_FROM_RECORDER] is True
    assert sensor_entry.data[CONF_ATTRIBUTES] == {"source": "sensor-options"}
    state = hass.states.get("sensor.office_temperature")
    assert state is not None
    assert state.state == "26.5"
    assert state.attributes["source"] == "sensor-options"


async def test_binary_sensor_options_update_entry_and_live_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Persist binary sensor options and reload its state and attributes."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: "configured_binary",
            CONF_NAME: "Configured Binary",
            CONF_VALUE: "true",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "binary_sensor_options"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_VALUE: "false",
            CONF_ATTRIBUTES: {"source": "binary-options-form"},
            "device_class": "door",
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: True,
            CONF_EXCLUDE_FROM_RECORDER: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_VALUE] == "false"
    assert entry.data["device_class"] == "door"
    assert entry.data[CONF_ATTRIBUTES] == {"source": "binary-options-form"}
    assert entry.data[CONF_RESTORE] is False
    assert entry.data[CONF_FORCE_UPDATE] is True
    assert entry.data[CONF_EXCLUDE_FROM_RECORDER] is False
    state = hass.states.get("binary_sensor.configured_binary")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["source"] == "binary-options-form"


async def test_device_tracker_options_update_entry_and_live_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Persist tracker options and reload its coordinates and attributes."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "configured_tracker",
            CONF_NAME: "Configured Tracker",
            CONF_YAML_VARIABLE: False,
            ATTR_LATITUDE: 40.0,
            ATTR_LONGITUDE: -75.0,
            ATTR_GPS_ACCURACY: 10,
            ATTR_BATTERY_LEVEL: 80,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "device_tracker_options"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_LATITUDE: 41.25,
            ATTR_LONGITUDE: -74.75,
            ATTR_LOCATION_NAME: "Studio",
            ATTR_GPS_ACCURACY: 4,
            ATTR_BATTERY_LEVEL: 65,
            CONF_ATTRIBUTES: {"source": "tracker-options-form"},
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: True,
            CONF_EXCLUDE_FROM_RECORDER: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[ATTR_LATITUDE] == 41.25
    assert entry.data[ATTR_LONGITUDE] == -74.75
    assert entry.data[ATTR_LOCATION_NAME] == "Studio"
    assert entry.data[CONF_ATTRIBUTES] == {"source": "tracker-options-form"}
    assert entry.data[CONF_RESTORE] is False
    assert entry.data[CONF_FORCE_UPDATE] is True
    assert entry.data[CONF_EXCLUDE_FROM_RECORDER] is False
    state = hass.states.get("device_tracker.configured_tracker")
    assert state is not None
    assert state.state == "Studio"
    assert state.attributes[ATTR_LATITUDE] == 41.25
    assert state.attributes[ATTR_LONGITUDE] == -74.75
    assert state.attributes[ATTR_GPS_ACCURACY] == 4
    assert state.attributes[ATTR_BATTERY_LEVEL] == 65
    assert state.attributes["source"] == "tracker-options-form"


async def test_sensor_entity_service_updates_state_and_attributes(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Mutate a loaded sensor through Home Assistant's registered entity service."""
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_SENSOR,
        {
            "entity_id": ["sensor.office_temperature"],
            CONF_VALUE: 19,
            ATTR_ATTRIBUTES: {"service_marker": True},
            ATTR_REPLACE_ATTRIBUTES: True,
        },
        blocking=True,
    )

    state = hass.states.get("sensor.office_temperature")
    assert state is not None
    assert state.state == "19"
    assert state.attributes["service_marker"] is True
    assert "source" not in state.attributes


async def test_binary_sensor_options_flow_changes_live_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Change binary state and attributes through the options workflow."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: "options_binary",
            CONF_NAME: "Options Binary",
            CONF_VALUE: "true",
            CONF_YAML_VARIABLE: False,
            "restore": False,
            "force_update": False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "change_binary_sensor_value"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_VALUE: "false", "attributes": {"source": "binary-options"}},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "value_changed"
    state = hass.states.get("binary_sensor.options_binary")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["source"] == "binary-options"


async def test_device_tracker_options_flow_changes_live_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Change tracker coordinates and metadata through the options workflow."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "options_tracker",
            CONF_NAME: "Options Tracker",
            CONF_YAML_VARIABLE: False,
            ATTR_LATITUDE: 40.0,
            ATTR_LONGITUDE: -75.0,
            ATTR_GPS_ACCURACY: 10,
            ATTR_BATTERY_LEVEL: 80,
            "restore": False,
            "force_update": False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "change_device_tracker_value"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_LATITUDE: 41.5,
            ATTR_LONGITUDE: -74.5,
            ATTR_GPS_ACCURACY: 6,
            ATTR_BATTERY_LEVEL: 72,
            "attributes": {"source": "tracker-options"},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "value_changed"
    state = hass.states.get("device_tracker.options_tracker")
    assert state is not None
    assert state.attributes[ATTR_LATITUDE] == 41.5
    assert state.attributes[ATTR_LONGITUDE] == -74.5
    assert state.attributes[ATTR_GPS_ACCURACY] == 6
    assert state.attributes[ATTR_BATTERY_LEVEL] == 72
    assert state.attributes["source"] == "tracker-options"


async def test_device_options_flow_updates_registry_metadata(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Persist device options and update the existing registry record."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: CONF_DEVICE,
            CONF_NAME: "Options Hub",
            CONF_YAML_VARIABLE: False,
            ATTR_MANUFACTURER: "Original",
            ATTR_MODEL: "Original Model",
            ATTR_CONFIGURATION_URL: "https://example.com/original",
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_MANUFACTURER: "Updated",
            ATTR_MODEL: "Updated Model",
            ATTR_CONFIGURATION_URL: "https://example.com/updated",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[ATTR_MANUFACTURER] == "Updated"
    assert entry.data[ATTR_MODEL] == "Updated Model"
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.manufacturer == "Updated"
    assert device.model == "Updated Model"
    assert str(device.configuration_url) == "https://example.com/updated"


async def test_device_options_invalid_url_preserves_entry_and_registry(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Keep device data unchanged when its options URL is invalid."""
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: CONF_DEVICE,
            CONF_NAME: "Preserved Hub",
            CONF_YAML_VARIABLE: False,
            ATTR_MANUFACTURER: "Original",
            ATTR_MODEL: "Original Model",
            ATTR_CONFIGURATION_URL: "https://example.com/original",
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = dr.async_get(hass)
    original_device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert original_device is not None
    original_data = dict(entry.data)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_MANUFACTURER: "Should Not Persist",
            ATTR_MODEL: "Should Not Persist",
            ATTR_CONFIGURATION_URL: "not a URL",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"
    assert result["errors"] == {"base": "invalid_url"}
    assert dict(entry.data) == original_data
    current_device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert current_device is not None
    assert current_device.id == original_device.id
    assert current_device.manufacturer == "Original"
    assert current_device.model == "Original Model"
    assert str(current_device.configuration_url) == "https://example.com/original"
