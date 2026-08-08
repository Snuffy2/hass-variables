"""Device registry helpers for the Variable integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_MODEL_ID,
    ATTR_SERIAL_NUMBER,
    ATTR_SW_VERSION,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_YAML_VARIABLE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def create_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create or update a Variable helper device.

    Args:
        hass (HomeAssistant): Home Assistant instance hosting the integration.
        entry (ConfigEntry): Variable config entry that defines the helper device.
    """
    # _LOGGER.debug(f"({entry.title}) [create_device] entry: {entry}")

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=entry.data.get(ATTR_MANUFACTURER),
        name=entry.data.get(CONF_NAME),
        model=entry.data.get(ATTR_MODEL),
        model_id=entry.data.get(ATTR_MODEL_ID),
        sw_version=entry.data.get(ATTR_SW_VERSION),
        hw_version=entry.data.get(ATTR_HW_VERSION),
        serial_number=entry.data.get(ATTR_SERIAL_NUMBER),
        configuration_url=entry.data.get(ATTR_CONFIGURATION_URL),
    )
    _LOGGER.debug("(%s) [create_device] device: %s", device.name, device)
    device_entities = er.async_entries_for_device(
        registry=entity_registry, device_id=device.id, include_disabled_entities=True
    )
    # _LOGGER.debug(f"({device.name}) [create_device] device entities: {device_entities}")

    domain_entries = hass.config_entries.async_loaded_entries(DOMAIN)
    # _LOGGER.debug(f"({device.name}) [create_device] domain_entries: {domain_entries}")
    domain_entities: list = []
    for domain_entry in domain_entries:
        # _LOGGER.debug(f"({device.name}) [create_device] domain_entry: {entry}")
        # _LOGGER.debug(f"({device.name}) [create_device] domain_entry data: {entry.data}")
        if not domain_entry.data.get(CONF_YAML_VARIABLE, False):
            domain_entities = domain_entities + er.async_entries_for_config_entry(
                registry=entity_registry, config_entry_id=domain_entry.entry_id
            )
    # _LOGGER.debug(f"({device.name}) [create_device] domain entities: {domain_entities}")
    domain_reload_entities = [entity for entity in domain_entities if entity.device_id == device.id]
    reload_entities = device_entities + domain_reload_entities
    if len(reload_entities) > 0:
        _LOGGER.debug(
            "(%s) [create_device] Reloading %s entities", device.name, len(reload_entities)
        )
    else:
        _LOGGER.debug("(%s) [create_device] Reloading all Variable entities", device.name)
        reload_entities = domain_entities

    scheduled_entry_ids: set[str] = set()
    for entity in reload_entities:
        # May actually want to do this for all entities, will see
        if entity.platform != DOMAIN:
            continue
        _LOGGER.debug("(%s) [create_device] Reloading entity_id: %s", device.name, entity.entity_id)
        if entity.config_entry_id and entity.config_entry_id not in scheduled_entry_ids:
            scheduled_entry_ids.add(entity.config_entry_id)
            hass.config_entries.async_schedule_reload(entity.config_entry_id)


async def update_device(
    hass: HomeAssistant, entry: ConfigEntry, user_input: dict[str, Any]
) -> bool:
    """Update a Variable helper device.

    Args:
        hass (HomeAssistant): Home Assistant instance hosting the integration.
        entry (ConfigEntry): Variable config entry associated with the helper device.
        user_input (dict[str, Any]): Device registry fields to update.

    Returns:
        True when the device was updated; False when no matching device exists.
    """
    # _LOGGER.debug(f"({entry.title}) [update_device] entry: {entry}")
    # _LOGGER.debug(f"({entry.title}) [update_device] user_input: {user_input}")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    # _LOGGER.debug(f"({device.name}) [update_device] device: {device}")
    if device is None:
        _LOGGER.debug("No device found to update")
        return False

    device_registry.async_update_device(
        device_id=device.id,
        manufacturer=user_input.get(ATTR_MANUFACTURER),
        model=user_input.get(ATTR_MODEL),
        model_id=user_input.get(ATTR_MODEL_ID),
        sw_version=user_input.get(ATTR_SW_VERSION),
        hw_version=user_input.get(ATTR_HW_VERSION),
        serial_number=user_input.get(ATTR_SERIAL_NUMBER),
        configuration_url=user_input.get(ATTR_CONFIGURATION_URL),
    )
    _LOGGER.debug("(%s) [update_device] updated device: %s", device.name or "", device)
    return True


async def remove_device(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a Variable helper device.

    Args:
        hass (HomeAssistant): Home Assistant instance hosting the integration.
        entry (ConfigEntry): Variable config entry associated with the helper device.

    Returns:
        True after the matching device is removed or when none exists.
    """
    # _LOGGER.debug(f"({entry.title}) [remove_device] entry: {entry}")

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    _LOGGER.debug("(%s) [remove_device] device: %s", getattr(device, "name", ""), device)
    if device is None:
        return True
    entities = er.async_entries_for_device(
        registry=entity_registry, device_id=device.id, include_disabled_entities=True
    )
    _LOGGER.debug("(%s) [remove_device] Reloading %s entities", device.name, len(entities))
    device_registry.async_remove_device(device.id)

    for entity in entities:
        # May actually want to do this for all entities, will see
        if entity.platform != DOMAIN:
            continue
        _LOGGER.debug("(%s) [remove_device] Reloading entity_id: %s", device.name, entity.entity_id)
        if entity.config_entry_id:
            hass.config_entries.async_schedule_reload(entity.config_entry_id)

    return True
