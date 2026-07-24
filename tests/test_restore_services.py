"""Integration tests for restore lifecycle and entity service workflows."""

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.components.device_tracker.const import ATTR_LOCATION_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.variable.const import (
    ATTR_ATTRIBUTES,
    ATTR_DELETE_IN_ZONES,
    ATTR_DELETE_LOCATION_NAME,
    ATTR_REPLACE_ATTRIBUTES,
    ATTR_VALUE_DELTA,
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_VALUE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
    SERVICE_DECREMENT_SENSOR,
    SERVICE_INCREMENT_SENSOR,
    SERVICE_UPDATE_DEVICE_TRACKER,
)

ConfigEntryFactory = Callable[[Mapping[str, Any]], ConfigEntry]


@pytest.mark.parametrize(
    ("entry_data", "entity_id", "restored_state", "restored_attributes"),
    [
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.SENSOR,
                CONF_VARIABLE_ID: "restored_sensor",
                CONF_VALUE: 1,
                "value_type": "number",
            },
            "sensor.restored_sensor",
            "42.5",
            {"source": "sensor-cache"},
            id="sensor",
        ),
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
                CONF_VARIABLE_ID: "restored_binary",
                CONF_VALUE: "false",
            },
            "binary_sensor.restored_binary",
            STATE_ON,
            {"source": "binary-cache"},
            id="binary-sensor",
        ),
        pytest.param(
            {
                CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
                CONF_VARIABLE_ID: "restored_tracker",
                ATTR_LATITUDE: 40.0,
                ATTR_LONGITUDE: -75.0,
            },
            "device_tracker.restored_tracker",
            "Studio",
            {
                ATTR_LATITUDE: 41.25,
                ATTR_LONGITUDE: -74.75,
                ATTR_LOCATION_NAME: "Studio",
                "source": "tracker-cache",
            },
            id="device-tracker",
        ),
    ],
)
async def test_restore_cache_is_applied_during_config_entry_setup(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    entry_data: dict[str, Any],
    entity_id: str,
    restored_state: str,
    restored_attributes: dict[str, Any],
) -> None:
    """Restore each platform's public state and custom attributes on startup.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
        entry_data: Platform-specific variable configuration.
        entity_id: Expected restored entity identifier.
        restored_state: Cached state to restore.
        restored_attributes: Cached attributes to restore.
    """
    cached_state = State(entity_id, restored_state, restored_attributes)
    if entry_data[CONF_ENTITY_PLATFORM] is Platform.SENSOR:
        mock_restore_cache_with_extra_data(
            hass,
            [
                (
                    cached_state,
                    {
                        "native_value": restored_state,
                        "native_unit_of_measurement": None,
                    },
                )
            ],
        )
    else:
        mock_restore_cache(hass, [cached_state])
    entry = config_entry_factory(
        {
            **entry_data,
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: True,
            CONF_FORCE_UPDATE: False,
            CONF_ATTRIBUTES: {"source": "config"},
        }
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == restored_state
    assert state.attributes["source"] == restored_attributes["source"]
    for attribute in (ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_LOCATION_NAME):
        if attribute in restored_attributes:
            assert state.attributes[attribute] == restored_attributes[attribute]


@pytest.mark.parametrize(
    ("platform", "entity_id", "restored_state", "platform_data"),
    [
        pytest.param(
            Platform.SENSOR,
            "sensor.linked_temperature",
            "23",
            {CONF_VALUE: 0, "value_type": "number"},
            id="sensor",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            "binary_sensor.linked_contact",
            STATE_ON,
            {CONF_VALUE: "false"},
            id="binary-sensor",
        ),
        pytest.param(
            Platform.DEVICE_TRACKER,
            "device_tracker.linked_tracker",
            "Workshop",
            {ATTR_LOCATION_NAME: "Config Location"},
            id="device-tracker",
        ),
    ],
)
async def test_device_linked_name_is_not_prefixed_again_after_reload(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    platform: Platform,
    entity_id: str,
    restored_state: str,
    platform_data: dict[str, Any],
) -> None:
    """Keep each device-linked platform's friendly name stable across reload.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
        platform: Platform under test.
        entity_id: Entity identifier associated with the platform.
        restored_state: Cached state to restore.
        platform_data: Platform-specific variable configuration.
    """
    device_entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: CONF_DEVICE,
            CONF_NAME: "Virtual Hub",
            CONF_YAML_VARIABLE: False,
        }
    )
    assert await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, device_entry.entry_id)})
    assert device is not None

    entity_name = {
        Platform.SENSOR: "Linked Temperature",
        Platform.BINARY_SENSOR: "Linked Contact",
        Platform.DEVICE_TRACKER: "Linked Tracker",
    }[platform]
    friendly_name = f"Virtual Hub {entity_name}"
    cached_state = State(
        entity_id,
        restored_state,
        {
            ATTR_FRIENDLY_NAME: friendly_name,
            "source": "restore-cache",
        },
    )
    if platform is Platform.SENSOR:
        mock_restore_cache_with_extra_data(
            hass,
            [
                (
                    cached_state,
                    {
                        "native_value": restored_state,
                        "native_unit_of_measurement": None,
                    },
                )
            ],
        )
    else:
        mock_restore_cache(hass, [cached_state])
    entity_entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: platform,
            CONF_VARIABLE_ID: entity_id.split(".", maxsplit=1)[1],
            CONF_NAME: entity_name,
            CONF_DEVICE_ID: device.id,
            **platform_data,
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: True,
            CONF_FORCE_UPDATE: False,
        }
    )

    assert await hass.config_entries.async_setup(entity_entry.entry_id)
    await hass.async_block_till_done()
    initial = hass.states.get(entity_id)
    assert initial is not None
    assert initial.attributes[ATTR_FRIENDLY_NAME] == friendly_name

    assert await hass.config_entries.async_reload(entity_entry.entry_id)
    await hass.async_block_till_done()
    reloaded = hass.states.get(entity_id)
    assert reloaded is not None
    assert reloaded.attributes[ATTR_FRIENDLY_NAME] == friendly_name


async def test_sensor_increment_and_decrement_services(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Apply explicit and default deltas through registered sensor services.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
    """
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "service_counter",
            CONF_VALUE: 10,
            "value_type": "number",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INCREMENT_SENSOR,
        {"entity_id": ["sensor.service_counter"], ATTR_VALUE_DELTA: 2.5},
        blocking=True,
    )
    incremented = hass.states.get("sensor.service_counter")
    assert incremented is not None
    assert incremented.state == "12.5"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DECREMENT_SENSOR,
        {"entity_id": ["sensor.service_counter"]},
        blocking=True,
    )
    decremented = hass.states.get("sensor.service_counter")
    assert decremented is not None
    assert decremented.state == "11.5"


@pytest.mark.parametrize(
    "service",
    [SERVICE_INCREMENT_SENSOR, SERVICE_DECREMENT_SENSOR],
)
async def test_numeric_services_reject_string_sensor(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    service: str,
) -> None:
    """Reject numeric services for string sensors without changing their state.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
        service: Numeric service expected to reject the string sensor.
    """
    entity_id = "sensor.string_value"
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "string_value",
            CONF_VALUE: "unchanged",
            "value_type": "string",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ValueError, match="Cannot .* non-numeric variable"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"entity_id": [entity_id]},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unchanged"


@pytest.mark.parametrize(
    ("initial_value", "expected_state"),
    [
        pytest.param("true", STATE_OFF, id="on-to-off"),
        pytest.param("false", STATE_ON, id="off-to-on"),
        pytest.param(None, STATE_UNKNOWN, id="unknown-remains-unknown"),
    ],
)
async def test_binary_sensor_toggle_service(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    initial_value: str | None,
    expected_state: str,
) -> None:
    """Toggle known binary states while preserving the public unknown state.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
        initial_value: Initial variable value provided to the binary sensor.
        expected_state: Expected public state after toggling.
    """
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: f"toggle_{expected_state}",
            CONF_VALUE: initial_value,
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    entity_id = f"binary_sensor.toggle_{expected_state}"
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "toggle_binary_sensor",
        {"entity_id": [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_device_tracker_update_and_delete_services(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Update tracker location data, then delete its optional location fields.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
    """
    entity_id = "device_tracker.service_tracker"
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "service_tracker",
            ATTR_BATTERY_LEVEL: 80,
            CONF_ATTRIBUTES: {"retained": True},
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DEVICE_TRACKER,
        {
            "entity_id": [entity_id],
            ATTR_LOCATION_NAME: "Workshop",
            ATTR_BATTERY_LEVEL: 64,
            ATTR_LATITUDE: 41.5,
            ATTR_LONGITUDE: -74.5,
            ATTR_GPS_ACCURACY: 4,
            ATTR_ATTRIBUTES: {"updated": True},
            ATTR_REPLACE_ATTRIBUTES: False,
        },
        blocking=True,
    )
    updated = hass.states.get(entity_id)
    assert updated is not None
    assert updated.state == "Workshop"
    assert updated.attributes[ATTR_BATTERY_LEVEL] == 64
    assert updated.attributes[ATTR_LATITUDE] == 41.5
    assert updated.attributes[ATTR_LONGITUDE] == -74.5
    assert updated.attributes[ATTR_GPS_ACCURACY] == 4
    assert updated.attributes["retained"] is True
    assert updated.attributes["updated"] is True

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DEVICE_TRACKER,
        {
            "entity_id": [entity_id],
            ATTR_DELETE_LOCATION_NAME: True,
        },
        blocking=True,
    )
    deleted = hass.states.get(entity_id)
    assert deleted is not None
    assert ATTR_LOCATION_NAME not in deleted.attributes
    assert deleted.state != "Workshop"


async def test_device_tracker_in_zones_service_and_delete(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Set and delete a coordinate-free tracker's explicit zone membership.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
    """
    entity_id = "device_tracker.zone_tracker"
    zone_id = "zone.workshop"
    hass.states.async_set(
        zone_id,
        "zoning",
        {
            ATTR_FRIENDLY_NAME: "Workshop Zone",
            "latitude": 41.5,
            "longitude": -74.5,
            "radius": 100,
            "passive": False,
        },
    )
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "zone_tracker",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DEVICE_TRACKER,
        {"entity_id": [entity_id], "in_zones": [zone_id]},
        blocking=True,
    )
    zoned = hass.states.get(entity_id)
    assert zoned is not None
    assert zoned.state == "Workshop Zone"
    assert zoned.attributes["in_zones"] == [zone_id]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DEVICE_TRACKER,
        {"entity_id": [entity_id], ATTR_DELETE_IN_ZONES: True},
        blocking=True,
    )
    unzoned = hass.states.get(entity_id)
    assert unzoned is not None
    assert unzoned.state == STATE_UNKNOWN
    assert unzoned.attributes["in_zones"] == []
