"""End-to-end tests for Variable device orchestration and lifecycle behavior."""

from homeassistant.components.device_tracker.const import ATTR_LOCATION_NAME
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_CONFIGURATION_URL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MANUFACTURER,
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.variable.const import (
    CONF_ATTRIBUTES,
    CONF_CLEAR_DEVICE_ID,
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
from tests.types import ConfigEntryFactory


async def test_setup_device_entry_creates_registry_device(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Load a device config entry and register its metadata.

    Args:
        hass: Home Assistant instance that hosts the integration.
        config_entry_factory: Factory that creates the device config entry.
    """
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


async def test_clearing_variable_device_links_preserves_entities_when_device_removed(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Unlink every variable platform before removing its virtual device.

    Args:
        hass: Home Assistant test instance used for the lifecycle workflow.
        config_entry_factory: Factory that creates registered Variable entries.
    """
    flow_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    flow_result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"],
        user_input={"next_step_id": "add_device"},
    )
    flow_result = await hass.config_entries.flow.async_configure(
        flow_result["flow_id"],
        user_input={
            CONF_NAME: "Lifecycle Device",
            ATTR_MANUFACTURER: "Variables",
        },
    )

    assert flow_result["type"] is FlowResultType.CREATE_ENTRY
    device_entry = flow_result["result"]
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, device_entry.entry_id)})
    assert device is not None

    entries = [
        config_entry_factory(
            {
                CONF_ENTITY_PLATFORM: Platform.SENSOR,
                CONF_VARIABLE_ID: "linked_sensor",
                CONF_NAME: "Linked Sensor",
                CONF_VALUE: "21.5",
                CONF_VALUE_TYPE: "string",
                CONF_DEVICE_ID: device.id,
                CONF_YAML_VARIABLE: False,
                CONF_RESTORE: False,
                CONF_FORCE_UPDATE: False,
            }
        ),
        config_entry_factory(
            {
                CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
                CONF_VARIABLE_ID: "linked_binary",
                CONF_NAME: "Linked Binary",
                CONF_VALUE: "true",
                CONF_DEVICE_ID: device.id,
                CONF_YAML_VARIABLE: False,
                CONF_RESTORE: False,
                CONF_FORCE_UPDATE: False,
            }
        ),
        config_entry_factory(
            {
                CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
                CONF_VARIABLE_ID: "linked_tracker",
                CONF_NAME: "Linked Tracker",
                ATTR_LATITUDE: 40.0,
                ATTR_LONGITUDE: -75.0,
                ATTR_GPS_ACCURACY: 10,
                ATTR_BATTERY_LEVEL: 80,
                CONF_DEVICE_ID: device.id,
                CONF_YAML_VARIABLE: False,
                CONF_RESTORE: False,
                CONF_FORCE_UPDATE: False,
            }
        ),
    ]
    entity_ids = (
        "sensor.linked_sensor",
        "binary_sensor.linked_binary",
        "device_tracker.linked_tracker",
    )

    for entry in entries:
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id, entry in zip(entity_ids, entries, strict=True):
        assert hass.states.get(entity_id) is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_entry_id == entry.entry_id
        assert registry_entry.device_id == device.id

    sensor_flow = await hass.config_entries.options.async_init(entries[0].entry_id)
    sensor_flow = await hass.config_entries.options.async_configure(
        sensor_flow["flow_id"],
        user_input={"next_step_id": "sensor_options"},
    )
    assert sensor_flow["step_id"] == "sensor_options"
    sensor_flow = await hass.config_entries.options.async_configure(
        sensor_flow["flow_id"],
        user_input={
            CONF_DEVICE_CLASS: "None",
            CONF_CLEAR_DEVICE_ID: True,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_EXCLUDE_FROM_RECORDER: False,
        },
    )
    assert sensor_flow["step_id"] == "sensor_options_page_2"
    sensor_flow = await hass.config_entries.options.async_configure(
        sensor_flow["flow_id"],
        user_input={
            CONF_VALUE: "21.5",
            CONF_ATTRIBUTES: {"source": "sensor-options"},
        },
    )
    assert sensor_flow["type"] is FlowResultType.CREATE_ENTRY

    binary_flow = await hass.config_entries.options.async_init(entries[1].entry_id)
    binary_flow = await hass.config_entries.options.async_configure(
        binary_flow["flow_id"],
        user_input={"next_step_id": "binary_sensor_options"},
    )
    binary_flow = await hass.config_entries.options.async_configure(
        binary_flow["flow_id"],
        user_input={
            CONF_VALUE: "true",
            CONF_ATTRIBUTES: {"source": "binary-options"},
            CONF_DEVICE_CLASS: "None",
            CONF_CLEAR_DEVICE_ID: True,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_EXCLUDE_FROM_RECORDER: False,
        },
    )
    assert binary_flow["type"] is FlowResultType.CREATE_ENTRY

    tracker_flow = await hass.config_entries.options.async_init(entries[2].entry_id)
    tracker_flow = await hass.config_entries.options.async_configure(
        tracker_flow["flow_id"],
        user_input={"next_step_id": "device_tracker_options"},
    )
    tracker_flow = await hass.config_entries.options.async_configure(
        tracker_flow["flow_id"],
        user_input={
            ATTR_LATITUDE: 40.0,
            ATTR_LONGITUDE: -75.0,
            ATTR_LOCATION_NAME: "Test Location",
            ATTR_GPS_ACCURACY: 10,
            ATTR_BATTERY_LEVEL: 80,
            CONF_ATTRIBUTES: {"source": "tracker-options"},
            CONF_CLEAR_DEVICE_ID: True,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_EXCLUDE_FROM_RECORDER: False,
        },
    )
    assert tracker_flow["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    for entity_id, entry in zip(entity_ids, entries, strict=True):
        assert CONF_DEVICE_ID not in entry.data
        assert hass.states.get(entity_id) is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_entry_id == entry.entry_id
        assert registry_entry.device_id is None

    assert await hass.config_entries.async_remove(device_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, device_entry.entry_id)}) is None
    for entity_id, entry in zip(entity_ids, entries, strict=True):
        assert hass.states.get(entity_id) is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_entry_id == entry.entry_id
        assert registry_entry.device_id is None
