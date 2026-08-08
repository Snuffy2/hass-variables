"""Variable implementation for Home Assistant."""

from collections.abc import Mapping
import contextlib
import copy
import logging
from typing import Any

from homeassistant.components import sensor as ha_sensor
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_NAME,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    ATTR_ATTRIBUTES,
    ATTR_ENTITY,
    ATTR_REPLACE_ATTRIBUTES,
    ATTR_VALUE,
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
    DEFAULT_REPLACE_ATTRIBUTES,
    DEFAULT_RESTORE,
    DOMAIN,
    PLATFORMS,
    SERVICE_UPDATE_SENSOR,
)
from .device import create_device, remove_device

try:
    from homeassistant.helpers.helper_integration import async_remove_helper_devices
except ImportError:
    from homeassistant.helpers.device import async_remove_stale_devices_links_keep_current_device

    def async_remove_helper_devices(
        hass: HomeAssistant,
        *,
        helper_config_entry_id: str,
        source_device_id: str | None,
        remove_all_devices: bool = False,
    ) -> None:
        """Remove stale helper device links on Home Assistant releases before 2026.8.

        Args:
            hass: Home Assistant instance hosting the helper integration.
            helper_config_entry_id: Config entry identifier for the helper.
            source_device_id: Device identifier that should remain linked.
            remove_all_devices: Ignored on legacy Home Assistant releases.
        """
        async_remove_stale_devices_links_keep_current_device(
            hass,
            helper_config_entry_id,
            source_device_id,
        )


_LOGGER = logging.getLogger(__name__)

SERVICE_SET_VARIABLE_LEGACY = "set_variable"
SERVICE_SET_ENTITY_LEGACY = "set_entity"

SERVICE_SET_VARIABLE_LEGACY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VARIABLE): cv.string,
        vol.Optional(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_ATTRIBUTES): dict,
        vol.Optional(ATTR_REPLACE_ATTRIBUTES, default=DEFAULT_REPLACE_ATTRIBUTES): cv.boolean,
    }
)

SERVICE_SET_ENTITY_LEGACY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY): cv.string,
        vol.Optional(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_ATTRIBUTES): dict,
        vol.Optional(ATTR_REPLACE_ATTRIBUTES, default=DEFAULT_REPLACE_ATTRIBUTES): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                cv.string: vol.Schema(
                    {
                        vol.Optional(CONF_ATTRIBUTES): dict,
                        vol.Optional(CONF_EXCLUDE_FROM_RECORDER): cv.boolean,
                        vol.Optional(CONF_FORCE_UPDATE): cv.boolean,
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_RESTORE): cv.boolean,
                        vol.Optional(CONF_VALUE): cv.match_all,
                    },
                    extra=vol.ALLOW_EXTRA,
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the Variable services."""

    async def async_set_variable_legacy_service(call: ServiceCall) -> None:
        """Handle calls to the set_variable legacy service."""

        # _LOGGER.debug(f"[async_set_variable_legacy_service] Pre call data: {call.data}")
        ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"
        var_ent = ENTITY_ID_FORMAT.format(call.data.get(ATTR_VARIABLE))
        # _LOGGER.debug(f"[async_set_variable_legacy_service] Post call data: {call.data}")
        await _async_set_legacy_service(call, var_ent)

    async def async_set_entity_legacy_service(call: ServiceCall) -> None:
        """Handle calls to the set_entity legacy service."""

        # _LOGGER.debug(f"[async_set_entity_legacy_service] call data: {call.data}")
        entity = call.data.get(ATTR_ENTITY)
        if not entity or not isinstance(entity, str):
            _LOGGER.error("set_entity legacy service called without valid 'entity' string")
            return
        await _async_set_legacy_service(call, entity)

    async def _async_set_legacy_service(call: ServiceCall, var_ent: str):
        """Shared function for both set_entity and set_variable legacy services."""

        # _LOGGER.debug(f"[async_set_legacy_service] call data: {call.data}")
        update_sensor_data = {
            CONF_ENTITY_ID: [var_ent],
            ATTR_REPLACE_ATTRIBUTES: call.data.get(ATTR_REPLACE_ATTRIBUTES, False),
        }
        if call.data.get(ATTR_VALUE):
            update_sensor_data.update({ATTR_VALUE: call.data.get(ATTR_VALUE)})
        if call.data.get(ATTR_ATTRIBUTES):
            update_sensor_data.update({ATTR_ATTRIBUTES: call.data.get(ATTR_ATTRIBUTES)})
        _LOGGER.debug(f"[async_set_legacy_service] update_sensor_data: {update_sensor_data}")
        await hass.services.async_call(
            DOMAIN, SERVICE_UPDATE_SENSOR, service_data=update_sensor_data
        )

    async def _async_reload_service_handler(service: ServiceCall) -> None:
        """Handle reload service call."""
        _LOGGER.info("Service %s.reload called: reloading YAML integration", DOMAIN)
        reload_config = None
        with contextlib.suppress(HomeAssistantError):
            reload_config = await async_integration_yaml_config(hass, DOMAIN)
        if reload_config is None:
            return
        _LOGGER.debug(f" reload_config: {reload_config}")
        await _async_process_yaml(hass, reload_config)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VARIABLE_LEGACY,
        async_set_variable_legacy_service,
        schema=SERVICE_SET_VARIABLE_LEGACY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ENTITY_LEGACY,
        async_set_entity_legacy_service,
        schema=SERVICE_SET_ENTITY_LEGACY_SCHEMA,
    )
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, _async_reload_service_handler)

    return await _async_process_yaml(hass, config, wait_for_completion=False)


async def _async_process_yaml(
    hass: HomeAssistant,
    config: ConfigType,
    *,
    wait_for_completion: bool = True,
) -> bool:
    """Reconcile YAML-defined variables with their config entries.

    Args:
        hass: Home Assistant instance that hosts the integration.
        config: Complete Home Assistant configuration containing this domain.
        wait_for_completion: Whether to wait for config-entry lifecycle work.
            This must be false during initial integration setup to avoid a
            config-entry setup cycle.

    Returns:
        True after all YAML imports, updates, and removals have completed.
    """
    variables = copy.deepcopy(config.get(DOMAIN, {}))
    entries_by_variable_id: dict[str, list[ConfigEntry]] = {}
    yaml_entries_by_variable_id: dict[str, list[ConfigEntry]] = {}

    for entry in hass.config_entries.async_entries(DOMAIN):
        variable_id = entry.data.get(CONF_VARIABLE_ID)
        if not isinstance(variable_id, str):
            continue
        entries_by_variable_id.setdefault(variable_id, []).append(entry)
        if entry.data.get(CONF_YAML_VARIABLE, False):
            yaml_entries_by_variable_id.setdefault(variable_id, []).append(entry)

    for var, var_fields in variables.items():
        if var is not None:
            _LOGGER.debug(f"[YAML] variable_id: {var}")
            _LOGGER.debug(f"[YAML] var_fields: {var_fields}")

            for key_empty, var_empty in var_fields.copy().items():
                if var_empty is None:
                    var_fields.pop(key_empty)

            yaml_entries = yaml_entries_by_variable_id.get(var, [])
            if any(
                not entry.data.get(CONF_YAML_VARIABLE, False)
                for entry in entries_by_variable_id.get(var, [])
            ):
                _LOGGER.error(
                    "[YAML] Cannot import %s because that variable ID belongs to a UI-created entry",
                    var,
                )
                for entry in yaml_entries:
                    remove_entry = hass.config_entries.async_remove(entry.entry_id)
                    if wait_for_completion:
                        await remove_entry
                    else:
                        hass.async_create_task(remove_entry)
                continue

            if not yaml_entries:
                _LOGGER.warning("[YAML] Creating New Sensor Variable: %s", var)
                import_flow = hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=_yaml_entry_data(var, var_fields),
                )
                if wait_for_completion:
                    await import_flow
                else:
                    hass.async_create_task(import_flow)
            else:
                _LOGGER.info("[YAML] Updating Existing Sensor Variable: %s", var)
                entry = yaml_entries[0]
                for duplicate_entry in yaml_entries[1:]:
                    remove_entry = hass.config_entries.async_remove(duplicate_entry.entry_id)
                    if wait_for_completion:
                        await remove_entry
                    else:
                        hass.async_create_task(remove_entry)
                yaml_data = _yaml_entry_data(var, var_fields)
                hass.config_entries.async_update_entry(entry, data=yaml_data)
                reload_entry = hass.config_entries.async_reload(entry.entry_id)
                if wait_for_completion:
                    await reload_entry
                else:
                    hass.async_create_task(reload_entry)

    # Remove any config entries that were originally created from YAML imports
    # but are no longer present in the current YAML configuration.
    yaml_variable_ids = set(variables)
    for entries in yaml_entries_by_variable_id.values():
        for entry in entries:
            variable_id = entry.data.get(CONF_VARIABLE_ID)
            if variable_id not in yaml_variable_ids:
                _LOGGER.warning(
                    "[YAML] YAML Entry no longer exists in configuration, deleting entry: %s",
                    variable_id,
                )
                remove_entry = hass.config_entries.async_remove(entry.entry_id)
                if wait_for_completion:
                    await remove_entry
                else:
                    hass.async_create_task(remove_entry)

    return True


def _yaml_entry_data(variable_id: str, variable_config: Mapping[str, Any]) -> dict[str, object]:
    """Build the complete config-entry data owned by one YAML variable.

    Args:
        variable_id: YAML mapping key that identifies the variable.
        variable_config: Configuration supplied for that variable.

    Returns:
        Config entry data which contains only the current YAML settings and
        required YAML provenance fields.
    """
    yaml_config = copy.deepcopy(dict(variable_config))
    attributes = yaml_config.pop(CONF_ATTRIBUTES, {})
    icon = attributes.pop(CONF_ICON, None)
    name = yaml_config.pop(CONF_NAME, attributes.pop(CONF_FRIENDLY_NAME, None))
    attributes.pop(CONF_FRIENDLY_NAME, None)

    entry_data: dict[str, object] = {
        CONF_ENTITY_PLATFORM: Platform.SENSOR,
        CONF_VARIABLE_ID: variable_id,
        CONF_YAML_VARIABLE: True,
        CONF_ATTRIBUTES: attributes,
        CONF_RESTORE: DEFAULT_RESTORE,
    }
    for key in (
        CONF_VALUE,
        CONF_RESTORE,
        CONF_FORCE_UPDATE,
        CONF_EXCLUDE_FROM_RECORDER,
    ):
        value = yaml_config.get(key)
        if value is not None:
            entry_data[key] = value
    if name is not None:
        entry_data[CONF_NAME] = name
    if icon is not None:
        entry_data[CONF_ICON] = icon

    device_class = attributes.get(CONF_DEVICE_CLASS)
    if device_class == ha_sensor.SensorDeviceClass.DATE:
        entry_data[CONF_VALUE_TYPE] = "date"
    elif device_class == ha_sensor.SensorDeviceClass.TIMESTAMP:
        entry_data[CONF_VALUE_TYPE] = "datetime"
    elif device_class in (
        ha_sensor.SensorDeviceClass.MONETARY,
        ha_sensor.SensorDeviceClass.ENUM,
    ):
        entry_data[CONF_VALUE_TYPE] = "string"
    elif device_class is not None:
        entry_data[CONF_VALUE_TYPE] = "number"

    return entry_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # _LOGGER.debug(f"[init async_setup_entry] entry: {entry.data}")
    if entry.data.get(CONF_YAML_PRESENT) is True:
        yaml_data = copy.deepcopy(dict(entry.data))
        yaml_data.pop(CONF_YAML_PRESENT, None)
        hass.config_entries.async_update_entry(entry, data=yaml_data, options={})

    # UI-driven option changes only; YAML entries are managed via _async_process_yaml.
    if not entry.data.get(CONF_YAML_VARIABLE, False):

        async def _async_on_entry_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
            """Handle config entry update."""
            _LOGGER.debug(f"Config entry updated: {entry.data.get(CONF_VARIABLE_ID)}")
            await hass.config_entries.async_reload(entry.entry_id)

        entry.async_on_unload(entry.add_update_listener(_async_on_entry_update))

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    hass.data[DOMAIN][entry.entry_id] = hass_data
    platform = hass_data.get(CONF_ENTITY_PLATFORM)
    if platform in PLATFORMS:
        async_remove_helper_devices(
            hass,
            helper_config_entry_id=entry.entry_id,
            source_device_id=entry.data.get(CONF_DEVICE_ID),
            remove_all_devices=True,
        )
        await hass.config_entries.async_forward_entry_setups(entry, [platform])
    elif hass_data.get(CONF_ENTITY_PLATFORM) == CONF_DEVICE:
        await create_device(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.info(f"Unloading: {entry.data}")
    # _LOGGER.debug(f"[init async_unload_entry] entry: {entry}")
    hass_data = dict(entry.data)
    unload_ok = False
    platform = hass_data.get(CONF_ENTITY_PLATFORM)
    if platform in PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, [platform])
    elif platform == CONF_DEVICE:
        unload_ok = await remove_device(hass, entry)
    if unload_ok:
        # Remove stored hass data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove entity registry entries tied to a config entry.

    Args:
        hass: Home Assistant instance that hosts the integration.
        entry: Config entry being permanently removed.
    """
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    for entity_entry in entries:
        _LOGGER.debug(
            f"Removing entity registry entry for removed config: {entity_entry.entity_id}"
        )
        registry.async_remove(entity_entry.entity_id)
