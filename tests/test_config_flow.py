"""Integration tests for the Variable config flow."""

import datetime
from typing import Any

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.sensor.const import CONF_STATE_CLASS
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
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.variable.const import (
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_EXCLUDE_FROM_RECORDER,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_TZOFFSET,
    CONF_VALUE,
    CONF_VALUE_TYPE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
)


async def _start_sensor_flow(
    hass: HomeAssistant, page_1_input: dict[str, Any]
) -> config_entries.ConfigFlowResult:
    """Start a sensor flow and submit its first page."""
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
        result["flow_id"], user_input=page_1_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_page_2"
    return result


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


@pytest.mark.parametrize(
    (
        "variable_id",
        "device_class",
        "page_2_input",
        "expected_value_type",
        "expected_value",
        "expected_state",
        "expected_attributes",
    ),
    [
        pytest.param(
            "typed_date",
            SensorDeviceClass.DATE,
            {CONF_VALUE: "2026-07-23", CONF_ATTRIBUTES: {"source": "flow"}},
            "date",
            datetime.date(2026, 7, 23),
            "2026-07-23",
            {"device_class": SensorDeviceClass.DATE, "source": "flow"},
            id="date",
        ),
        pytest.param(
            "typed_timestamp_positive",
            SensorDeviceClass.TIMESTAMP,
            {
                CONF_VALUE: "2026-07-23 10:15:00",
                CONF_TZOFFSET: "+0530",
                CONF_ATTRIBUTES: {"source": "flow"},
            },
            "datetime",
            datetime.datetime(
                2026,
                7,
                23,
                10,
                15,
                tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
            ),
            "2026-07-23T04:45:00+00:00",
            {"device_class": SensorDeviceClass.TIMESTAMP, "source": "flow"},
            id="timestamp-positive-offset",
        ),
        pytest.param(
            "typed_timestamp_negative",
            SensorDeviceClass.TIMESTAMP,
            {
                CONF_VALUE: "2026-07-23 10:15:00",
                CONF_TZOFFSET: "-0400",
                CONF_ATTRIBUTES: {"source": "flow"},
            },
            "datetime",
            datetime.datetime(
                2026,
                7,
                23,
                10,
                15,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-4)),
            ),
            "2026-07-23T14:15:00+00:00",
            {"device_class": SensorDeviceClass.TIMESTAMP, "source": "flow"},
            id="timestamp-negative-offset",
        ),
        pytest.param(
            "typed_temperature",
            SensorDeviceClass.TEMPERATURE,
            {
                CONF_VALUE: "21.5",
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_UNIT_OF_MEASUREMENT: "°C",
                CONF_ATTRIBUTES: {"source": "flow"},
            },
            "number",
            21.5,
            "21.5",
            {
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": "°C",
                "source": "flow",
            },
            id="measurement-temperature",
        ),
        pytest.param(
            "typed_money",
            SensorDeviceClass.MONETARY,
            {
                CONF_VALUE: "19.95",
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
                CONF_UNIT_OF_MEASUREMENT: "USD",
                CONF_ATTRIBUTES: {"source": "flow"},
            },
            "number",
            19.95,
            "19.95",
            {
                "device_class": SensorDeviceClass.MONETARY,
                "state_class": SensorStateClass.TOTAL,
                "unit_of_measurement": "USD",
                "source": "flow",
            },
            id="monetary",
        ),
    ],
)
async def test_typed_sensor_flow_matrix(
    hass: HomeAssistant,
    variable_id: str,
    device_class: SensorDeviceClass,
    page_2_input: dict[str, Any],
    expected_value_type: str,
    expected_value: object,
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Create typed sensors through the public flow and expose their live state."""
    result = await _start_sensor_flow(
        hass,
        {
            CONF_VARIABLE_ID: variable_id,
            CONF_NAME: variable_id.replace("_", " ").title(),
            CONF_DEVICE_CLASS: device_class,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=page_2_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_CLASS] == device_class
    assert result["data"][CONF_VALUE_TYPE] == expected_value_type
    assert result["data"][CONF_VALUE] == expected_value
    for key in (CONF_STATE_CLASS, CONF_UNIT_OF_MEASUREMENT, CONF_TZOFFSET):
        if key in page_2_input:
            assert result["data"][key] == page_2_input[key]

    await hass.async_block_till_done()
    entity_id = f"sensor.{variable_id}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert {key: state.attributes[key] for key in expected_attributes} == expected_attributes
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.config_entry_id == result["result"].entry_id


@pytest.mark.parametrize(
    ("variable_id", "device_class", "invalid_value", "raises_invalid_data"),
    [
        pytest.param(
            "bad_date",
            SensorDeviceClass.DATE,
            "2026-02-30",
            True,
            id="date",
        ),
        pytest.param(
            "bad_timestamp",
            SensorDeviceClass.TIMESTAMP,
            "not-a-timestamp",
            True,
            id="timestamp",
        ),
        pytest.param(
            "bad_numeric",
            SensorDeviceClass.TEMPERATURE,
            "warm",
            False,
            id="numeric",
        ),
    ],
)
async def test_typed_sensor_flow_rejects_incompatible_values(
    hass: HomeAssistant,
    variable_id: str,
    device_class: SensorDeviceClass,
    invalid_value: str,
    raises_invalid_data: bool,
) -> None:
    """Keep typed sensor flows open and entry-free for incompatible values."""
    result = await _start_sensor_flow(
        hass,
        {
            CONF_VARIABLE_ID: variable_id,
            CONF_DEVICE_CLASS: device_class,
        },
    )
    flow_id = result["flow_id"]
    if raises_invalid_data:
        with pytest.raises(InvalidData) as err:
            await hass.config_entries.flow.async_configure(
                flow_id, user_input={CONF_VALUE: invalid_value}
            )
        assert err.value.schema_errors[CONF_VALUE]
        result = await hass.config_entries.flow.async_configure(flow_id)
        assert result["errors"] == {}
    else:
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={CONF_VALUE: invalid_value}
        )
        assert result["errors"] == {"base": "invalid_value_type"}

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_page_2"
    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.states.get(f"sensor.{variable_id}") is None


@pytest.mark.parametrize(
    ("invalid_input", "error_key"),
    [
        pytest.param(
            {CONF_STATE_CLASS: SensorStateClass.TOTAL},
            CONF_STATE_CLASS,
            id="state-class",
        ),
        pytest.param(
            {CONF_UNIT_OF_MEASUREMENT: "USD"},
            CONF_UNIT_OF_MEASUREMENT,
            id="unit",
        ),
    ],
)
async def test_temperature_flow_rejects_invalid_typed_selection(
    hass: HomeAssistant,
    invalid_input: dict[str, Any],
    error_key: str,
) -> None:
    """Reject state classes and units not offered by the typed sensor page."""
    result = await _start_sensor_flow(
        hass,
        {
            CONF_VARIABLE_ID: f"bad_temperature_{error_key}",
            CONF_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    flow_id = result["flow_id"]

    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_VALUE: "21.5", **invalid_input},
        )

    assert error_key in err.value.schema_errors
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_page_2"
    assert not hass.config_entries.async_entries(DOMAIN)


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
