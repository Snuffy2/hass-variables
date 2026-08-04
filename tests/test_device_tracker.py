"""Integration tests for Variable device-tracker restore and services."""

from homeassistant.components.device_tracker.const import ATTR_LOCATION_NAME
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_NAME,
    STATE_NOT_HOME,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.variable.const import (
    ATTR_ATTRIBUTES,
    ATTR_DELETE_IN_ZONES,
    ATTR_DELETE_LOCATION_NAME,
    ATTR_REPLACE_ATTRIBUTES,
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
    SERVICE_UPDATE_DEVICE_TRACKER,
)
from tests.types import ConfigEntryFactory


async def test_device_tracker_restore_cache_is_applied_during_config_entry_setup(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Restore a tracker's public state and custom attributes on startup.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
    """
    entity_id = "device_tracker.restored_tracker"
    restored_state = "Studio"
    restored_attributes = {
        ATTR_LATITUDE: 41.25,
        ATTR_LONGITUDE: -74.75,
        ATTR_LOCATION_NAME: "Studio",
        "source": "tracker-cache",
    }
    cached_state = State(entity_id, restored_state, restored_attributes)
    mock_restore_cache(hass, [cached_state])
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "restored_tracker",
            ATTR_LATITUDE: 40.0,
            ATTR_LONGITUDE: -75.0,
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
        assert state.attributes[attribute] == restored_attributes[attribute]


async def test_device_linked_tracker_name_is_not_prefixed_again_after_reload(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Keep a device-linked tracker's friendly name stable across reload.

    Args:
        hass: Home Assistant test instance.
        config_entry_factory: Factory for test configuration entries.
    """
    entity_id = "device_tracker.linked_tracker"
    restored_state = "Workshop"
    entity_name = "Linked Tracker"
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

    friendly_name = f"Virtual Hub {entity_name}"
    cached_state = State(
        entity_id,
        restored_state,
        {
            ATTR_FRIENDLY_NAME: friendly_name,
            "source": "restore-cache",
        },
    )
    mock_restore_cache(hass, [cached_state])
    entity_entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.DEVICE_TRACKER,
            CONF_VARIABLE_ID: "linked_tracker",
            CONF_NAME: entity_name,
            CONF_DEVICE_ID: device.id,
            ATTR_LOCATION_NAME: "Config Location",
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
    assert deleted.state == STATE_NOT_HOME


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
