"""Integration tests for Variable binary-sensor restore and services."""

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
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
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.variable.const import (
    ATTR_ATTRIBUTES,
    ATTR_REPLACE_ATTRIBUTES,
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_VALUE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DOMAIN,
    SERVICE_UPDATE_BINARY_SENSOR,
)
from tests.types import ConfigEntryFactory


async def test_binary_sensor_restore_cache_is_applied_during_config_entry_setup(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Restore a binary sensor's public state and custom attributes on startup.

    Args:
        hass (HomeAssistant): Home Assistant test instance.
        config_entry_factory (ConfigEntryFactory): Factory for test configuration entries.
    """
    entity_id = "binary_sensor.restored_binary"
    restored_state = STATE_ON
    restored_attributes = {"source": "binary-cache"}
    cached_state = State(entity_id, restored_state, restored_attributes)
    mock_restore_cache(hass, [cached_state])
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: "restored_binary",
            CONF_VALUE: "false",
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


async def test_device_linked_binary_sensor_name_is_not_prefixed_again_after_reload(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Keep a device-linked binary sensor's friendly name stable across reload.

    Args:
        hass (HomeAssistant): Home Assistant test instance.
        config_entry_factory (ConfigEntryFactory): Factory for test configuration entries.
    """
    entity_id = "binary_sensor.linked_contact"
    restored_state = STATE_ON
    entity_name = "Linked Contact"
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
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: "linked_contact",
            CONF_NAME: entity_name,
            CONF_DEVICE_ID: device.id,
            CONF_VALUE: "false",
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


@pytest.mark.parametrize(
    ("initial_value", "expected_state", "variable_suffix"),
    [
        pytest.param("true", STATE_OFF, "on_to_off", id="on-to-off"),
        pytest.param("false", STATE_ON, "off_to_on", id="off-to-on"),
        pytest.param(None, STATE_UNKNOWN, "unknown", id="unknown-remains-unknown"),
    ],
)
async def test_binary_sensor_toggle_service(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    initial_value: str | None,
    expected_state: str,
    variable_suffix: str,
) -> None:
    """Toggle known binary states while preserving the public unknown state.

    Args:
        hass (HomeAssistant): Home Assistant test instance.
        config_entry_factory (ConfigEntryFactory): Factory for test configuration entries.
        initial_value (str | None): Initial variable value provided to the binary sensor.
        expected_state (str): Expected public state after toggling.
        variable_suffix (str): Stable suffix for the test variable and entity IDs.
    """
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: f"toggle_{variable_suffix}",
            CONF_VALUE: initial_value,
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    entity_id = f"binary_sensor.toggle_{variable_suffix}"
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


@pytest.mark.parametrize(
    ("value", "expected_state"),
    [
        pytest.param("true", STATE_ON, id="true"),
        pytest.param("1", STATE_ON, id="one"),
        pytest.param("yes", STATE_ON, id="yes"),
        pytest.param("on", STATE_ON, id="on"),
        pytest.param("false", STATE_OFF, id="false"),
        pytest.param("0", STATE_OFF, id="zero"),
        pytest.param("none", STATE_UNKNOWN, id="none"),
        pytest.param("unavailable", STATE_UNKNOWN, id="unavailable"),
        pytest.param(None, STATE_UNKNOWN, id="null"),
        pytest.param(True, STATE_ON, id="bool-true"),
        pytest.param(False, STATE_OFF, id="bool-false"),
    ],
)
async def test_update_binary_sensor_value_coercion_matrix(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    value: str | bool | None,
    expected_state: str,
) -> None:
    """Coerce update_binary_sensor values across supported truthy aliases.

    Args:
        hass (HomeAssistant): Home Assistant test instance.
        config_entry_factory (ConfigEntryFactory): Factory for test configuration entries.
        value (str | bool | None): Service payload value to coerce.
        expected_state (str): Expected public binary state after the update.
    """
    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR,
            CONF_VARIABLE_ID: "coercion_binary",
            CONF_VALUE: "false",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_ATTRIBUTES: {"source": "initial"},
        }
    )
    entity_id = "binary_sensor.coercion_binary"
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_BINARY_SENSOR,
        {
            "entity_id": [entity_id],
            CONF_VALUE: value,
            ATTR_ATTRIBUTES: {"source": "coerced"},
            ATTR_REPLACE_ATTRIBUTES: False,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["source"] == "coerced"
