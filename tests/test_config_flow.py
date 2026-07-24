"""Integration tests for the Variable config flow."""

from typing import Any

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_CONFIGURATION_URL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MANUFACTURER,
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.variable.const import (
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_EXCLUDE_FROM_RECORDER,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_VALUE,
    CONF_VALUE_TYPE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
)


async def test_user_flow_menu(hass: HomeAssistant) -> None:
    """Expose every supported config-entry workflow from the user menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [
        "add_sensor",
        "add_binary_sensor",
        "add_device_tracker",
        "add_device",
    ]


async def test_sensor_flow_creates_typed_entry(hass: HomeAssistant) -> None:
    """Create a numeric sensor through both pages of the real flow API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_VARIABLE_ID: "outside_temperature",
            CONF_NAME: "Outside Temperature",
            CONF_ICON: "mdi:thermometer",
            CONF_DEVICE_CLASS: "temperature",
            CONF_RESTORE: True,
            CONF_FORCE_UPDATE: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_page_2"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_VALUE: "23.5",
            CONF_ATTRIBUTES: {"source": "flow"},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Outside Temperature"
    assert result["data"] == {
        CONF_VARIABLE_ID: "outside_temperature",
        CONF_NAME: "Outside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_DEVICE_CLASS: "temperature",
        CONF_RESTORE: True,
        CONF_FORCE_UPDATE: False,
        CONF_EXCLUDE_FROM_RECORDER: False,
        CONF_ENTITY_PLATFORM: Platform.SENSOR,
        CONF_YAML_VARIABLE: False,
        CONF_VALUE_TYPE: "number",
        CONF_VALUE: 23.5,
        CONF_ATTRIBUTES: {"source": "flow"},
    }
    await hass.async_block_till_done()
    state = hass.states.get("sensor.outside_temperature")
    assert state is not None
    assert state.state == "23.5"
    assert state.attributes["source"] == "flow"
    registry_entry = er.async_get(hass).async_get("sensor.outside_temperature")
    assert registry_entry is not None
    assert registry_entry.config_entry_id == result["result"].entry_id


async def test_sensor_flow_rejects_incompatible_value(hass: HomeAssistant) -> None:
    """Keep the sensor flow open when its value cannot match its type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_sensor"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_VARIABLE_ID: "bad_number",
            CONF_DEVICE_CLASS: "temperature",
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VALUE: "not-a-number"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_page_2"
    assert result["errors"] == {"base": "invalid_value_type"}


@pytest.mark.parametrize(
    ("step_id", "user_input", "expected_platform", "expected_entity_id", "expected_state"),
    [
        pytest.param(
            "add_binary_sensor",
            {
                CONF_VARIABLE_ID: "garage_open",
                CONF_NAME: "Garage Open",
                CONF_VALUE: "true",
                CONF_DEVICE_CLASS: BinarySensorDeviceClass.GARAGE_DOOR,
            },
            Platform.BINARY_SENSOR,
            "binary_sensor.garage_open",
            "on",
            id="binary-sensor",
        ),
        pytest.param(
            "add_device_tracker",
            {
                CONF_VARIABLE_ID: "test_tracker",
                CONF_NAME: "Test Tracker",
                ATTR_LATITUDE: 40.0,
                ATTR_LONGITUDE: -75.0,
                ATTR_GPS_ACCURACY: 12,
                ATTR_BATTERY_LEVEL: 87,
            },
            Platform.DEVICE_TRACKER,
            "device_tracker.test_tracker",
            "not_home",
            id="device-tracker",
        ),
        pytest.param(
            "add_device",
            {
                CONF_NAME: "Virtual Hub",
                ATTR_MANUFACTURER: "Variables",
                ATTR_CONFIGURATION_URL: "https://example.com/device",
            },
            CONF_DEVICE,
            None,
            None,
            id="device",
        ),
    ],
)
async def test_single_page_flows_create_entries(
    hass: HomeAssistant,
    step_id: str,
    user_input: dict[str, Any],
    expected_platform: str,
    expected_entity_id: str | None,
    expected_state: str | None,
) -> None:
    """Create and fully set up each single-page config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": step_id}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ENTITY_PLATFORM] == expected_platform
    assert result["data"][CONF_YAML_VARIABLE] is False
    await hass.async_block_till_done()

    entry = result["result"]
    if expected_entity_id is not None:
        state = hass.states.get(expected_entity_id)
        assert state is not None
        assert state.state == expected_state
        registry_entry = er.async_get(hass).async_get(expected_entity_id)
        assert registry_entry is not None
        assert registry_entry.config_entry_id == entry.entry_id
    else:
        device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        assert device is not None
        assert device.name == "Virtual Hub"
        assert device.manufacturer == "Variables"
        assert str(device.configuration_url) == "https://example.com/device"


async def test_device_flow_rejects_invalid_configuration_url(hass: HomeAssistant) -> None:
    """Report an invalid URL without creating a device config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_device"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Invalid Device",
            ATTR_CONFIGURATION_URL: "not a URL",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_device"
    assert result["errors"] == {"base": "invalid_url"}
