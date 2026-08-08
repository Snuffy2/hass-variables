"""End-to-end setup orchestration tests for the Variable integration."""

import datetime
import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
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
    CONF_YAML_PRESENT,
    CONF_YAML_VARIABLE,
    DEFAULT_RESTORE,
    DOMAIN,
)
from tests.types import ConfigEntryFactory


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
                CONF_RESTORE: False,
                "attributes": {"source": "reload"},
            }
        }
    }
    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value=reloaded_config),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

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


async def test_yaml_reload_removes_duplicate_yaml_entries(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Retain one updated YAML entry and fully remove its duplicate.

    Args:
        hass: Home Assistant instance that hosts the integration.
        config_entry_factory: Factory that creates registered config entries.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    entries = [
        config_entry_factory(
            {
                CONF_ENTITY_PLATFORM: Platform.SENSOR,
                CONF_VARIABLE_ID: "duplicate_yaml",
                CONF_VALUE: value,
                CONF_VALUE_TYPE: "string",
                CONF_YAML_VARIABLE: True,
                CONF_RESTORE: False,
                CONF_FORCE_UPDATE: False,
                CONF_ATTRIBUTES: {"source": source},
            }
        )
        for value, source in (("retained", "canonical"), ("removed", "duplicate"))
    ]
    for entry in entries:
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    registry_entries = [
        er.async_entries_for_config_entry(registry, entry.entry_id)[0] for entry in entries
    ]
    for registry_entry in registry_entries:
        assert hass.states.get(registry_entry.entity_id) is not None

    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(
            return_value={
                DOMAIN: {
                    "duplicate_yaml": {
                        CONF_VALUE: "updated",
                        CONF_RESTORE: False,
                        CONF_ATTRIBUTES: {"source": "reload"},
                    }
                }
            }
        ),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    retained_entry = hass.config_entries.async_get_entry(entries[0].entry_id)
    assert retained_entry is not None
    assert retained_entry.data[CONF_VALUE] == "updated"
    assert hass.config_entries.async_get_entry(entries[1].entry_id) is None
    assert [
        entry.entry_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == "duplicate_yaml"
    ] == [entries[0].entry_id]
    assert registry.async_get(registry_entries[1].entity_id) is None
    assert hass.states.get(registry_entries[1].entity_id) is None
    retained_registry_entry = registry.async_get(registry_entries[0].entity_id)
    assert retained_registry_entry is not None
    retained_state = hass.states.get(retained_registry_entry.entity_id)
    assert retained_state is not None
    assert retained_state.state == "updated"
    assert retained_state.attributes["source"] == "reload"


@pytest.mark.parametrize(
    (
        "variable_id",
        "yaml_config",
        "entity_id",
        "expected_state",
        "expected_value_type",
    ),
    [
        pytest.param(
            "yaml_number",
            {CONF_VALUE: 42},
            "sensor.yaml_number",
            "42",
            None,
            id="number",
        ),
        pytest.param(
            "yaml_date",
            {
                CONF_VALUE: datetime.date(2026, 8, 5),
                CONF_ATTRIBUTES: {"device_class": "date"},
            },
            "sensor.yaml_date",
            "2026-08-05",
            "date",
            id="native-date",
        ),
        pytest.param(
            "yaml_enum",
            {
                CONF_VALUE: "heating",
                CONF_ATTRIBUTES: {"device_class": "enum"},
            },
            "sensor.yaml_enum",
            "heating",
            "string",
            id="enum",
        ),
    ],
)
async def test_yaml_reload_creates_entities_before_service_returns(
    hass: HomeAssistant,
    variable_id: str,
    yaml_config: dict[str, Any],
    entity_id: str,
    expected_state: str,
    expected_value_type: str | None,
) -> None:
    """Create YAML entities synchronously through the reload service.

    Args:
        hass: Home Assistant instance that hosts the integration.
        variable_id: YAML variable ID to import.
        yaml_config: Configuration for the imported YAML variable.
        entity_id: Expected entity identifier after import.
        expected_state: Expected state after import.
        expected_value_type: Expected stored value type, if any.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value={DOMAIN: {variable_id: yaml_config}}),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    assert entry.data[CONF_YAML_VARIABLE] is True
    assert entry.data[CONF_VALUE] == yaml_config[CONF_VALUE]
    if expected_value_type is None:
        assert CONF_VALUE_TYPE not in entry.data
    else:
        assert entry.data[CONF_VALUE_TYPE] == expected_value_type
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("initial_config", "removed_key", "removed_attribute"),
    [
        pytest.param({CONF_VALUE: 12}, CONF_VALUE, None, id="value"),
        pytest.param({CONF_FORCE_UPDATE: True}, CONF_FORCE_UPDATE, None, id="force-update"),
        pytest.param(
            {CONF_EXCLUDE_FROM_RECORDER: True},
            CONF_EXCLUDE_FROM_RECORDER,
            None,
            id="exclude-from-recorder",
        ),
        pytest.param(
            {CONF_NAME: "Configured Name"},
            CONF_NAME,
            None,
            id="name",
        ),
        pytest.param(
            {CONF_ATTRIBUTES: {CONF_FRIENDLY_NAME: "Configured Name"}},
            CONF_NAME,
            None,
            id="friendly-name-attribute",
        ),
        pytest.param(
            {CONF_ATTRIBUTES: {CONF_ICON: "mdi:thermometer"}},
            CONF_ICON,
            None,
            id="icon-attribute",
        ),
        pytest.param(
            {CONF_ATTRIBUTES: {"obsolete": "setting"}},
            None,
            "obsolete",
            id="attribute",
        ),
    ],
)
async def test_yaml_reload_removes_omitted_settings(
    hass: HomeAssistant,
    initial_config: dict[str, Any],
    removed_key: str | None,
    removed_attribute: str | None,
) -> None:
    """Replace prior YAML data rather than retaining omitted settings.

    Args:
        hass: Home Assistant instance that hosts the integration.
        initial_config: Initial settings that the later YAML omits.
        removed_key: Config-entry key expected to be removed on reload.
        removed_attribute: Entity attribute expected to be removed on reload.
    """
    variable_id = "yaml_settings"
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {variable_id: initial_config}})
    await hass.async_block_till_done()

    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value={DOMAIN: {variable_id: {CONF_RESTORE: False}}}),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    if removed_key is not None:
        assert removed_key not in entry.data
    if removed_attribute is not None:
        state = hass.states.get(f"sensor.{variable_id}")
        assert state is not None
        assert removed_attribute not in state.attributes


async def test_yaml_reload_restores_default_when_restore_is_omitted(
    hass: HomeAssistant,
) -> None:
    """Enable state restoration when reloaded YAML omits the restore setting.

    Args:
        hass: Home Assistant instance that hosts the integration.
    """
    variable_id = "yaml_restore_default"
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {variable_id: {CONF_RESTORE: False}}},
    )
    await hass.async_block_till_done()

    restore_lookup = AsyncMock(return_value=None)
    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value={DOMAIN: {variable_id: {}}}),
        ),
        patch(
            "custom_components.variable.sensor.Variable.async_get_last_sensor_data",
            new=restore_lookup,
        ),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    assert entry.data[CONF_RESTORE] is DEFAULT_RESTORE
    restore_lookup.assert_awaited_once_with()


@pytest.mark.parametrize("yaml_entry_present", [False, True], ids=["ui-only", "with-yaml"])
async def test_yaml_reload_does_not_overwrite_ui_created_entry(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    yaml_entry_present: bool,
) -> None:
    """Leave a UI-created entry unchanged when YAML uses its variable ID.

    Args:
        hass: Home Assistant instance that hosts the integration.
        config_entry_factory: Factory that creates registered config entries.
        yaml_entry_present: Whether a stale YAML-owned entry also exists.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    ui_entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "shared_variable",
            CONF_NAME: "UI Variable",
            CONF_VALUE: "ui-value",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_ATTRIBUTES: {"source": "ui"},
        }
    )
    assert await hass.config_entries.async_setup(ui_entry.entry_id)
    yaml_entry = None
    if yaml_entry_present:
        yaml_entry = config_entry_factory(
            {
                CONF_ENTITY_PLATFORM: Platform.SENSOR,
                CONF_VARIABLE_ID: "shared_variable",
                CONF_NAME: "YAML Variable",
                CONF_VALUE: "stale-yaml-value",
                CONF_YAML_VARIABLE: True,
                CONF_RESTORE: False,
                CONF_FORCE_UPDATE: False,
                CONF_ATTRIBUTES: {"source": "yaml"},
            }
        )
        assert await hass.config_entries.async_setup(yaml_entry.entry_id)
    await hass.async_block_till_done()
    original_data = dict(ui_entry.data)
    registry = er.async_get(hass)
    ui_registry_entry = er.async_entries_for_config_entry(registry, ui_entry.entry_id)[0]
    ui_state = hass.states.get(ui_registry_entry.entity_id)
    assert ui_state is not None
    assert ui_state.state == "ui-value"
    yaml_registry_entry = None
    if yaml_entry is not None:
        yaml_registry_entry = er.async_entries_for_config_entry(registry, yaml_entry.entry_id)[0]
        yaml_state = hass.states.get(yaml_registry_entry.entity_id)
        assert yaml_state is not None
        assert yaml_state.state == "stale-yaml-value"

    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value={DOMAIN: {"shared_variable": {CONF_VALUE: "yaml-value"}}}),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    current_entry = hass.config_entries.async_get_entry(ui_entry.entry_id)
    assert current_entry is not None
    assert dict(current_entry.data) == original_data
    if yaml_entry is not None:
        assert hass.config_entries.async_get_entry(yaml_entry.entry_id) is None
    assert [entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)] == [
        ui_entry.entry_id
    ]
    if yaml_registry_entry is not None:
        assert registry.async_get(yaml_registry_entry.entity_id) is None
        assert hass.states.get(yaml_registry_entry.entity_id) is None
    assert registry.async_get(ui_registry_entry.entity_id) == ui_registry_entry
    ui_state = hass.states.get(ui_registry_entry.entity_id)
    assert ui_state is not None
    assert ui_state.state == "ui-value"


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


async def test_unload_entry_removes_active_entity(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Unload a platform entry and remove its active entity state.

    Args:
        hass: Home Assistant instance that hosts the integration.
        sensor_entry: Sensor config entry to set up and unload.
    """
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_temperature") is not None

    assert await hass.config_entries.async_unload(sensor_entry.entry_id)
    await hass.async_block_till_done()

    unloaded_state = hass.states.get("sensor.office_temperature")
    assert unloaded_state is not None
    assert unloaded_state.state == STATE_UNAVAILABLE


async def test_setup_entry_calls_helper_device_cleanup(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Call helper device cleanup before forwarding platform setup.

    Args:
        hass: Home Assistant instance that hosts the integration.
        sensor_entry: Sensor config entry to set up.
        monkeypatch: Pytest fixture used to stub helper cleanup.
    """
    cleanup = MagicMock()
    monkeypatch.setattr(
        "custom_components.variable.async_remove_helper_devices",
        cleanup,
    )

    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()

    cleanup.assert_any_call(
        hass,
        helper_config_entry_id=sensor_entry.entry_id,
        source_device_id=sensor_entry.data.get("device_id"),
        remove_all_devices=True,
    )


def test_async_remove_helper_devices_fallback_maps_keyword_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Map the 2026.8 helper cleanup API onto the legacy device helper.

    Args:
        monkeypatch: Pytest fixture used to simulate missing helper APIs.
    """
    stale_calls: list[tuple[str, str | None]] = []

    def fake_stale(
        _hass: HomeAssistant,
        helper_config_entry_id: str,
        source_device_id: str | None,
    ) -> None:
        stale_calls.append((helper_config_entry_id, source_device_id))

    import homeassistant.helpers.helper_integration as helper_integration

    variable_module = importlib.import_module("custom_components.variable")

    monkeypatch.setattr(
        "homeassistant.helpers.device.async_remove_stale_devices_links_keep_current_device",
        fake_stale,
    )
    monkeypatch.delattr(helper_integration, "async_remove_helper_devices", raising=False)

    variable_module = importlib.reload(variable_module)
    try:
        variable_module.async_remove_helper_devices(
            None,
            helper_config_entry_id="entry-1",
            source_device_id="device-1",
            remove_all_devices=True,
        )
        assert stale_calls == [("entry-1", "device-1")]
    finally:
        importlib.reload(variable_module)


async def test_remove_entry_cleans_up_entity_registry(
    hass: HomeAssistant,
    sensor_entry: ConfigEntry,
) -> None:
    """Remove a config entry and clean up its entity registry record.

    Args:
        hass: Home Assistant instance that hosts the integration.
        sensor_entry: Sensor config entry to set up and remove.
    """
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get("sensor.office_temperature") is not None

    await hass.config_entries.async_remove(sensor_entry.entry_id)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get("sensor.office_temperature") is None
