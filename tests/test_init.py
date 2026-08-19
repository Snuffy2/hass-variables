"""End-to-end setup orchestration tests for the Variable integration."""

import asyncio
import datetime
import importlib
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntry, ConfigFlowContext
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, helper_integration
from homeassistant.setup import async_setup_component
import pytest

from custom_components.variable.const import (
    ATTR_ATTRIBUTES,
    ATTR_ENTITY,
    ATTR_REPLACE_ATTRIBUTES,
    ATTR_VARIABLE,
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


async def test_yaml_explicit_name_precedes_friendly_name_attribute(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Prefer an explicit name and omit the friendly-name attribute.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    yaml_config = {
        DOMAIN: {
            "named_variable": {
                CONF_NAME: "Explicit Name",
                CONF_ATTRIBUTES: {
                    CONF_FRIENDLY_NAME: "private-friendly-name",
                    "retained": True,
                    "private_attribute": "private-attribute-value",
                },
                CONF_VALUE: "private-yaml-value",
            }
        }
    }

    with caplog.at_level("DEBUG", logger="custom_components.variable"):
        assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data[CONF_NAME] == "Explicit Name"
    assert entry.data[CONF_ATTRIBUTES] == {
        "retained": True,
        "private_attribute": "private-attribute-value",
    }
    integration_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.variable"
    )
    assert "[YAML] variable_id: named_variable" in integration_logs
    assert "private-yaml-value" not in integration_logs
    assert "private-attribute-value" not in integration_logs


async def test_yaml_setup_and_reload_manage_config_entries(
    hass: HomeAssistant,
) -> None:
    """Create, update, and remove YAML variables through Home Assistant APIs.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
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


async def test_yaml_reload_does_not_log_configuration_values(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep YAML configuration values out of reload logs.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    initial_config = {
        DOMAIN: {
            "yaml_reload_secret": {
                CONF_VALUE: "initial-secret-value",
                CONF_ATTRIBUTES: {"source": "initial-secret-attribute"},
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    reloaded_config = {
        DOMAIN: {
            "yaml_reload_secret": {
                CONF_VALUE: "reload-secret-value",
                CONF_ATTRIBUTES: {"source": "reload-secret-attribute"},
            }
        }
    }
    caplog.clear()
    with (
        caplog.at_level("DEBUG", logger="custom_components.variable"),
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=reloaded_config),
        ),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    integration_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.variable"
    )
    assert "Reloading YAML variables: count=1" in integration_logs
    assert "reload-secret-value" not in integration_logs
    assert "reload-secret-attribute" not in integration_logs
    assert "initial-secret-value" not in integration_logs
    assert "initial-secret-attribute" not in integration_logs


@pytest.mark.parametrize(
    ("failed_lifecycle_method", "expected_call_count"),
    [("async_unload_entry", 1), ("async_setup_entry", 2)],
    ids=["unload-failure", "setup-failure"],
)
async def test_yaml_reload_rolls_back_when_config_entry_reload_fails(
    hass: HomeAssistant,
    failed_lifecycle_method: str,
    expected_call_count: int,
) -> None:
    """Restore config-entry data and live state after a failed YAML update.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        failed_lifecycle_method (str): Integration lifecycle method that rejects the
            first config-entry reload.
        expected_call_count (int): Lifecycle calls expected after rollback recovery.
    """
    variable_id = "yaml_rollback"
    initial_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "accepted",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "accepted"},
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    previous_data = dict(entry.data)
    entity_id = f"sensor.{variable_id}"
    initial_state = hass.states.get(entity_id)
    assert initial_state is not None
    assert initial_state.state == "accepted"

    variable_module = importlib.import_module("custom_components.variable")
    original_lifecycle_method = getattr(variable_module, failed_lifecycle_method)
    call_count = 0

    async def fail_first_lifecycle_call(
        lifecycle_hass: HomeAssistant, lifecycle_entry: ConfigEntry
    ) -> bool:
        """Reject the update reload, then allow the rollback reload.

        Args:
            lifecycle_hass (HomeAssistant): Home Assistant instance under test.
            lifecycle_entry (ConfigEntry): Config entry being reloaded.

        Returns:
            bool: False for the first call, then the real lifecycle result.
        """
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        return await original_lifecycle_method(lifecycle_hass, lifecycle_entry)

    rejected_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "rejected",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "rejected"},
            }
        }
    }
    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=rejected_config),
        ),
        patch.object(
            variable_module,
            failed_lifecycle_method,
            new=fail_first_lifecycle_call,
        ),
        pytest.raises(HomeAssistantError, match="restored its prior configuration"),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    assert call_count == expected_call_count
    current_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert current_entry is not None
    assert current_entry.data == previous_data
    recovered_state = hass.states.get(entity_id)
    assert recovered_state is not None
    assert recovered_state.state == "accepted"
    assert recovered_state.attributes["source"] == "accepted"


@pytest.mark.parametrize(
    ("failed_lifecycle_method", "expected_call_count"),
    [("async_unload_entry", 1), ("async_setup_entry", 2)],
    ids=["unload-failure", "setup-failure"],
)
async def test_startup_yaml_update_rolls_back_after_background_reload_failure(
    hass: HomeAssistant,
    failed_lifecycle_method: str,
    expected_call_count: int,
) -> None:
    """Recover prior entry data and live state after startup reload failure.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        failed_lifecycle_method (str): Integration lifecycle method that rejects the
            first background reload.
        expected_call_count (int): Lifecycle calls expected after rollback recovery.
    """
    variable_id = "startup_yaml_rollback"
    initial_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "accepted",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "accepted"},
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    entry = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    previous_data = dict(entry.data)

    entity_id = f"sensor.{variable_id}"
    initial_state = hass.states.get(entity_id)
    assert initial_state is not None
    assert initial_state.state == "accepted"

    variable_module = importlib.import_module("custom_components.variable")
    original_lifecycle_method = getattr(variable_module, failed_lifecycle_method)
    call_count = 0

    async def fail_first_lifecycle_call(
        lifecycle_hass: HomeAssistant, lifecycle_entry: ConfigEntry
    ) -> bool:
        """Reject the startup update reload, then allow recovery.

        Args:
            lifecycle_hass (HomeAssistant): Home Assistant instance under test.
            lifecycle_entry (ConfigEntry): Config entry being reloaded.

        Returns:
            bool: False for the first call, then the real lifecycle result.
        """
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        return await original_lifecycle_method(lifecycle_hass, lifecycle_entry)

    rejected_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "rejected",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "rejected"},
            }
        }
    }
    with patch.object(
        variable_module,
        failed_lifecycle_method,
        new=fail_first_lifecycle_call,
    ):
        assert await variable_module._async_process_yaml(
            hass, rejected_config, wait_for_completion=False
        )
        await hass.async_block_till_done()

    assert call_count == expected_call_count
    current_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert current_entry is not None
    assert current_entry.data == previous_data
    recovered_state = hass.states.get(entity_id)
    assert recovered_state is not None
    assert recovered_state.state == "accepted"
    assert recovered_state.attributes["source"] == "accepted"
    assert not hass.data[variable_module._YAML_LIFECYCLE_TASKS]


async def test_yaml_reload_removes_duplicate_yaml_entries(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
) -> None:
    """Retain one updated YAML entry and fully remove its duplicate.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        config_entry_factory (ConfigEntryFactory): Factory that creates registered config entries.
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
        pytest.param(
            "yaml_timestamp",
            {
                CONF_VALUE: datetime.datetime(2026, 8, 11, 12, 0, tzinfo=datetime.UTC),
                CONF_ATTRIBUTES: {"device_class": "timestamp"},
            },
            "sensor.yaml_timestamp",
            "2026-08-11T12:00:00+00:00",
            "datetime",
            id="timestamp",
        ),
        pytest.param(
            "yaml_temperature",
            {
                CONF_VALUE: 21.5,
                CONF_ATTRIBUTES: {"device_class": "temperature"},
            },
            "sensor.yaml_temperature",
            "21.5",
            "number",
            id="temperature",
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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        variable_id (str): YAML variable ID to import.
        yaml_config (dict[str, Any]): Configuration for the imported YAML variable.
        entity_id (str): Expected entity identifier after import.
        expected_state (str): Expected state after import.
        expected_value_type (str | None): Expected stored value type, if any.
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


async def test_concurrent_yaml_reloads_create_one_entry(
    hass: HomeAssistant,
) -> None:
    """Serialize concurrent reloads before they snapshot config entries.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    variable_id = "concurrent_yaml"
    reload_config = {DOMAIN: {variable_id: {CONF_VALUE: "created-once"}}}
    import_started = asyncio.Event()
    allow_import = asyncio.Event()
    original_async_init = hass.config_entries.flow.async_init

    async def blocking_async_init(*args: Any, **kwargs: Any) -> Any:
        """Pause the first import so the second reload overlaps it.

        Args:
            args (Any): Positional arguments for the real flow initializer.
            kwargs (Any): Keyword arguments for the real flow initializer.

        Returns:
            Any: Result from the real flow initializer.
        """
        import_started.set()
        await allow_import.wait()
        return await original_async_init(*args, **kwargs)

    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=reload_config),
        ),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            new=AsyncMock(side_effect=blocking_async_init),
        ) as async_init,
    ):
        reloads = asyncio.gather(
            hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True),
            hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True),
        )
        try:
            await import_started.wait()
            await asyncio.sleep(0)
            import_count_during_overlap = async_init.await_count
        finally:
            allow_import.set()
            await reloads

    assert import_count_during_overlap == 1

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    ]
    assert len(entries) == 1
    assert len(er.async_entries_for_config_entry(er.async_get(hass), entries[0].entry_id)) == 1
    state = hass.states.get(f"sensor.{variable_id}")
    assert state is not None
    assert state.state == "created-once"


async def test_startup_import_and_reload_create_one_entry(
    hass: HomeAssistant,
) -> None:
    """Wait for a pending startup import before a reload snapshots entries.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
    """
    variable_id = "startup_overlap"
    yaml_config = {DOMAIN: {variable_id: {CONF_VALUE: "created-once"}}}
    import_started = asyncio.Event()
    allow_import = asyncio.Event()
    original_async_init = hass.config_entries.flow.async_init

    async def blocking_async_init(*args: Any, **kwargs: Any) -> Any:
        """Pause the startup import at the config-entry creation boundary.

        Args:
            args (Any): Positional arguments for the real flow initializer.
            kwargs (Any): Keyword arguments for the real flow initializer.

        Returns:
            Any: Result from the real flow initializer.
        """
        import_started.set()
        await allow_import.wait()
        return await original_async_init(*args, **kwargs)

    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=yaml_config),
        ),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            new=AsyncMock(side_effect=blocking_async_init),
        ) as async_init,
    ):
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await import_started.wait()

        reload_task = asyncio.create_task(
            hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        )
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert async_init.await_count == 1
            assert not reload_task.done()
        finally:
            allow_import.set()
            await reload_task

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_VARIABLE_ID) == variable_id
    ]
    assert len(entries) == 1
    assert len(er.async_entries_for_config_entry(er.async_get(hass), entries[0].entry_id)) == 1
    state = hass.states.get(f"sensor.{variable_id}")
    assert state is not None
    assert state.state == "created-once"


async def test_reload_propagates_pending_startup_import_failure(
    hass: HomeAssistant,
) -> None:
    """Fail a reload when the startup lifecycle work it awaits fails.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
    """
    yaml_config = {DOMAIN: {"failed_startup": {CONF_VALUE: "unused"}}}
    import_started = asyncio.Event()
    allow_failure = asyncio.Event()

    async def failing_async_init(
        handler: str,
        *,
        context: ConfigFlowContext | None = None,
        data: Any = None,
    ) -> NoReturn:
        """Pause and then fail the startup import.

        Args:
            handler (str): Integration domain that owns the import flow.
            context (ConfigFlowContext | None): Optional flow initialization context.
            data (Any): Optional flow initialization data.

        Raises:
            RuntimeError: Always, after the test releases the failure gate.
        """
        import_started.set()
        await allow_failure.wait()
        raise RuntimeError("startup import failed")

    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=yaml_config),
        ),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            new=AsyncMock(side_effect=failing_async_init),
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await import_started.wait()
        reload_task = asyncio.create_task(
            hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        )
        await asyncio.sleep(0)
        allow_failure.set()
        with pytest.raises(RuntimeError, match="startup import failed"):
            await reload_task


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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        initial_config (dict[str, Any]): Initial settings that the later YAML omits.
        removed_key (str | None): Config-entry key expected to be removed on reload.
        removed_attribute (str | None): Entity attribute expected to be removed on reload.
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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        config_entry_factory (ConfigEntryFactory): Factory that creates registered config entries.
        yaml_entry_present (bool): Whether a stale YAML-owned entry also exists.
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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        config_entry_factory (ConfigEntryFactory): Factory that creates the platform config entry.
        data (dict[str, Any]): Platform-specific config-entry data to load.
        entity_id (str): Expected entity identifier after setup.
        expected_state (str): Expected state value for the created entity.
        expected_attributes (dict[str, Any]): Expected attributes for the created entity.
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unload a platform entry and remove its active entity state.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        sensor_entry (ConfigEntry): Sensor config entry to set up and unload.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.office_temperature") is not None

    caplog.clear()
    with caplog.at_level("INFO", logger="custom_components.variable"):
        assert await hass.config_entries.async_unload(sensor_entry.entry_id)
    await hass.async_block_till_done()
    integration_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.variable"
    )
    assert sensor_entry.entry_id in integration_logs
    assert sensor_entry.data[CONF_VARIABLE_ID] not in integration_logs

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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        sensor_entry (ConfigEntry): Sensor config entry to set up.
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to stub helper cleanup.
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
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to simulate missing helper APIs.
    """
    stale_calls: list[tuple[str, str | None]] = []

    def fake_stale(
        _hass: HomeAssistant,
        helper_config_entry_id: str,
        source_device_id: str | None,
    ) -> None:
        stale_calls.append((helper_config_entry_id, source_device_id))

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
            keep_device_ids={"device-1"},
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
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        sensor_entry (ConfigEntry): Sensor config entry to set up and remove.
    """
    assert await hass.config_entries.async_setup(sensor_entry.entry_id)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get("sensor.office_temperature") is not None

    await hass.config_entries.async_remove(sensor_entry.entry_id)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get("sensor.office_temperature") is None


async def test_legacy_set_variable_and_set_entity_update_sensor(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Route legacy set_variable/set_entity calls through update_sensor.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        config_entry_factory (ConfigEntryFactory): Factory that creates the sensor config entry.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "legacy_counter",
            CONF_VALUE: 5,
            CONF_VALUE_TYPE: "number",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
            CONF_ATTRIBUTES: {"source": "initial"},
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level("DEBUG", logger="custom_components.variable"):
        await hass.services.async_call(
            DOMAIN,
            "set_variable",
            {
                ATTR_VARIABLE: "legacy_counter",
                CONF_VALUE: 0,
                ATTR_ATTRIBUTES: {"source": "private-legacy-attribute"},
                ATTR_REPLACE_ATTRIBUTES: True,
            },
            blocking=True,
        )
    set_variable_state = hass.states.get("sensor.legacy_counter")
    assert set_variable_state is not None
    assert set_variable_state.state == "0"
    assert set_variable_state.attributes["source"] == "private-legacy-attribute"
    integration_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.variable"
    )
    assert "update fields" in integration_logs
    assert ATTR_ATTRIBUTES in integration_logs
    assert "private-legacy-attribute" not in integration_logs

    await hass.services.async_call(
        DOMAIN,
        "set_entity",
        {
            ATTR_ENTITY: "sensor.legacy_counter",
            CONF_VALUE: 3,
            ATTR_ATTRIBUTES: {"merged": True},
            ATTR_REPLACE_ATTRIBUTES: False,
        },
        blocking=True,
    )
    set_entity_state = hass.states.get("sensor.legacy_counter")
    assert set_entity_state is not None
    assert set_entity_state.state == "3"
    assert set_entity_state.attributes["source"] == "private-legacy-attribute"
    assert set_entity_state.attributes["merged"] is True


async def test_legacy_set_entity_rejects_invalid_entity(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ignore invalid set_entity targets without mutating existing sensors.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        config_entry_factory (ConfigEntryFactory): Factory that creates the sensor config entry.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    entry = config_entry_factory(
        {
            CONF_ENTITY_PLATFORM: Platform.SENSOR,
            CONF_VARIABLE_ID: "legacy_guard",
            CONF_VALUE: 11,
            CONF_VALUE_TYPE: "number",
            CONF_YAML_VARIABLE: False,
            CONF_RESTORE: False,
            CONF_FORCE_UPDATE: False,
        }
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with caplog.at_level("ERROR"):
        await hass.services.async_call(
            DOMAIN,
            "set_entity",
            {ATTR_ENTITY: "", CONF_VALUE: 99},
            blocking=True,
        )

    state = hass.states.get("sensor.legacy_guard")
    assert state is not None
    assert state.state == "11"
    assert "set_entity legacy service called without valid 'entity' string" in caplog.text


async def test_yaml_reload_exits_when_yaml_config_unavailable(
    hass: HomeAssistant,
) -> None:
    """Leave existing YAML entities unchanged when reload YAML is unavailable.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
    """
    variable_id = "yaml_reload_missing"
    initial_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "kept",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "initial"},
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    entry = next(
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    previous_data = dict(entry.data)
    entity_id = f"sensor.{variable_id}"
    initial_state = hass.states.get(entity_id)
    assert initial_state is not None
    assert initial_state.state == "kept"

    with patch(
        "custom_components.variable.async_integration_yaml_config",
        new=AsyncMock(return_value=None),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    current_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert current_entry is not None
    assert dict(current_entry.data) == previous_data
    current_state = hass.states.get(entity_id)
    assert current_state is not None
    assert current_state.state == "kept"
    assert current_state.attributes["source"] == "initial"


@pytest.mark.parametrize(
    ("rollback_failure", "log_fragment"),
    [
        pytest.param(
            False,
            "Reload returned false",
            id="reload-false",
        ),
        pytest.param(
            HomeAssistantError("rollback reload rejected"),
            "Error reloading",
            id="reload-raises",
        ),
    ],
)
async def test_yaml_reload_reports_failed_rollback_reload(
    hass: HomeAssistant,
    rollback_failure: bool | HomeAssistantError,
    log_fragment: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Restore prior data and log when the rollback reload itself fails.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
        rollback_failure (bool | HomeAssistantError): Second reload outcome that should be logged.
        log_fragment (str): Expected log text for the rollback failure mode.
        caplog (pytest.LogCaptureFixture): Pytest fixture capturing log output.
    """
    variable_id = "yaml_rollback_secondary"
    initial_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "accepted",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "accepted"},
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, initial_config)
    await hass.async_block_till_done()

    entry = next(
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.data.get(CONF_VARIABLE_ID) == variable_id
    )
    previous_data = dict(entry.data)
    entity_id = f"sensor.{variable_id}"
    call_count = 0

    async def fail_update_then_rollback(
        entry_id: str,
    ) -> bool:
        """Reject the updated reload, then fail the rollback reload.

        Args:
            entry_id (str): Config entry identifier passed by Home Assistant.

        Returns:
            bool: False when Home Assistant reports a rejected reload.

        Raises:
            rollback_failure: The parameterized Home Assistant rollback error.
        """
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        if isinstance(rollback_failure, HomeAssistantError):
            raise rollback_failure
        return False

    rejected_config = {
        DOMAIN: {
            variable_id: {
                CONF_VALUE: "rejected",
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "rejected"},
            }
        }
    }
    with (
        patch(
            "custom_components.variable.async_integration_yaml_config",
            new=AsyncMock(return_value=rejected_config),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            new=fail_update_then_rollback,
        ),
        caplog.at_level("ERROR"),
        pytest.raises(HomeAssistantError, match="restored its prior configuration"),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    assert call_count == 2
    assert log_fragment in caplog.text
    current_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert current_entry is not None
    assert dict(current_entry.data) == previous_data
    recovered_state = hass.states.get(entity_id)
    assert recovered_state is not None
    assert recovered_state.state == "accepted"


async def test_yaml_setup_drops_none_valued_fields(
    hass: HomeAssistant,
) -> None:
    """Omit YAML keys whose values are explicitly null.

    Args:
        hass (HomeAssistant): Home Assistant instance that hosts the integration.
    """
    yaml_config = {
        DOMAIN: {
            "yaml_null_fields": {
                CONF_VALUE: 7,
                CONF_ICON: None,
                CONF_RESTORE: False,
                CONF_ATTRIBUTES: {"source": "yaml"},
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data[CONF_VALUE] == 7
    assert CONF_ICON not in entry.data
    assert entry.data[CONF_ATTRIBUTES] == {"source": "yaml"}
