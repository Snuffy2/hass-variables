"""Device tracker platform for the Variable integration."""

from collections.abc import Mapping, MutableMapping
import copy
import logging
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import (
    ATTR_LOCATION_NAME,
    ATTR_SOURCE_TYPE,
    SourceType,
)
from homeassistant.components.device_tracker.legacy import PLATFORM_SCHEMA as LEGACY_PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_GPS_ACCURACY,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICE_ID,
    CONF_ICON,
    CONF_NAME,
    MATCH_ALL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_platform
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify
import voluptuous as vol
import yaml

from . import _async_exclude_entity_from_recorder
from .const import (
    ATTR_ATTRIBUTES,
    ATTR_DELETE_IN_ZONES,
    ATTR_DELETE_LOCATION_NAME,
    ATTR_REPLACE_ATTRIBUTES,
    CONF_ATTRIBUTES,
    CONF_EXCLUDE_FROM_RECORDER,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_UPDATED,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DEFAULT_EXCLUDE_FROM_RECORDER,
    DEFAULT_REPLACE_ATTRIBUTES,
    DOMAIN,
)
from .helpers import merge_attribute_dict

_LOGGER = logging.getLogger(__name__)

ATTR_IN_ZONES = "in_zones"

# Home Assistant 2026.6 added TrackerEntity.in_zones, which replaces using a
# free-form location name as the tracker state. Once the minimum version is
# 2026.6, remove this capability flag and the legacy mirror in
# _set_location_name, then assign only to _location_name.
SUPPORTS_TRACKER_IN_ZONES = hasattr(TrackerEntity, "in_zones")

PLATFORM = Platform.DEVICE_TRACKER
ENTITY_ID_FORMAT = PLATFORM + ".{}"
SERVICE_UPDATE_VARIABLE = "update_" + PLATFORM

PLATFORM_SCHEMA = LEGACY_PLATFORM_SCHEMA.extend({})

VARIABLE_ATTR_SETTINGS = {
    ATTR_FRIENDLY_NAME: "_attr_name",
    ATTR_ICON: "_attr_icon",
    ATTR_SOURCE_TYPE: "_attr_source_type",
    ATTR_LATITUDE: "_attr_latitude",
    ATTR_LONGITUDE: "_attr_longitude",
    ATTR_BATTERY_LEVEL: "_attr_battery_level",
    ATTR_IN_ZONES: "_attr_in_zones",
    ATTR_LOCATION_NAME: "_location_name",
    ATTR_GPS_ACCURACY: "_attr_gps_accuracy",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the Device Tracker Variable entity with a config_entry (config_flow)."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_UPDATE_VARIABLE,
        {
            vol.Optional(ATTR_LATITUDE): cv.latitude,
            vol.Optional(ATTR_LONGITUDE): cv.longitude,
            vol.Optional(ATTR_IN_ZONES): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_DELETE_IN_ZONES): cv.boolean,
            vol.Optional(ATTR_LOCATION_NAME): cv.string,
            vol.Optional(ATTR_DELETE_LOCATION_NAME): cv.boolean,
            vol.Optional(ATTR_GPS_ACCURACY): cv.positive_int,
            vol.Optional(ATTR_BATTERY_LEVEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(ATTR_ATTRIBUTES): dict,
            vol.Optional(ATTR_REPLACE_ATTRIBUTES, default=DEFAULT_REPLACE_ATTRIBUTES): cv.boolean,
        },
        "async_update_variable",
    )

    config = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
    unique_id = config_entry.entry_id
    # _LOGGER.debug(f"[async_setup_entry] config_entry: {config_entry.as_dict()}")
    # _LOGGER.debug(f"[async_setup_entry] config: {config}")
    # _LOGGER.debug(f"[async_setup_entry] unique_id: {unique_id}")

    if config.get(CONF_EXCLUDE_FROM_RECORDER, DEFAULT_EXCLUDE_FROM_RECORDER):
        _LOGGER.debug(
            "(%s) Excluding from Recorder.",
            config.get(CONF_NAME, config.get(CONF_VARIABLE_ID)),
        )
        async_add_entities([VariableNoRecorder(hass, config, config_entry, unique_id)])
    else:
        async_add_entities([Variable(hass, config, config_entry, unique_id)])


class Variable(RestoreEntity, TrackerEntity):
    """Class for the device tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        config_entry: ConfigEntry,
        unique_id: str,
    ) -> None:
        """Initialize a Device Tracker Variable."""
        super().__init__()
        self._hass = hass
        self._config = dict(config)
        self._config_entry = config_entry
        self._attr_has_entity_name = True
        self._variable_id = slugify(str(config.get(CONF_VARIABLE_ID, "")).lower())
        self._attr_unique_id = unique_id
        self._attr_name = config.get(CONF_NAME, config.get(CONF_VARIABLE_ID))
        self._attr_icon = config.get(CONF_ICON)
        self._restore = config.get(CONF_RESTORE)
        self._force_update = config.get(CONF_FORCE_UPDATE)
        self._yaml_variable = config.get(CONF_YAML_VARIABLE)
        self._exclude_from_recorder = config.get(CONF_EXCLUDE_FROM_RECORDER)
        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            self.device_entry = dr.async_get(hass).async_get(device_id)
        if (
            config.get(CONF_ATTRIBUTES) is not None
            and config.get(CONF_ATTRIBUTES)
            and isinstance(config.get(CONF_ATTRIBUTES), MutableMapping)
        ):
            self._attr_extra_state_attributes = self._update_attr_settings(
                config.get(CONF_ATTRIBUTES)
            )
        else:
            self._attr_extra_state_attributes = {}
        registry = er.async_get(self._hass)
        current_entity_id = registry.async_get_entity_id(DOMAIN, PLATFORM, self._attr_unique_id)
        if current_entity_id is not None:
            self.entity_id = current_entity_id
        else:
            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT, self._variable_id, hass=self._hass
            )
        _LOGGER.debug("(%s) [init] entity_id: %s", self._attr_name, self.entity_id)
        self._attr_source_type = config.get(ATTR_SOURCE_TYPE, SourceType.GPS)
        self._attr_latitude = config.get(ATTR_LATITUDE)
        self._attr_longitude = config.get(ATTR_LONGITUDE)
        self._attr_battery_level = config.get(ATTR_BATTERY_LEVEL)
        self._attr_in_zones = config.get(ATTR_IN_ZONES)
        self._set_location_name(config.get(ATTR_LOCATION_NAME))
        self._attr_gps_accuracy = config.get(ATTR_GPS_ACCURACY)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self._restore is True:
            _LOGGER.info("(%s) Restoring after Reboot", self._attr_name)
            state = await self.async_get_last_state()
            if state:
                _LOGGER.debug("(%s) Restored last state: %s", self._attr_name, state.as_dict())
                if (
                    hasattr(state, "attributes")
                    and state.attributes
                    and isinstance(state.attributes, MutableMapping)
                ):
                    # Avoid restoring Home Assistant's computed friendly_name back into
                    # _attr_name (it may already include the device name prefix).
                    restored_attributes = dict(state.attributes)
                    restored_attributes.pop(ATTR_FRIENDLY_NAME, None)
                    self._attr_extra_state_attributes = self._update_attr_settings(
                        restored_attributes,
                        just_pop=self._config.get(CONF_UPDATED, False),
                    )
                    _LOGGER.debug(
                        "(%s) [restored] attributes: %s",
                        self._attr_name,
                        self._attr_extra_state_attributes,
                    )
                    # If there were no attributes restored from state, apply attributes from config
                    if (
                        not getattr(self, "_attr_extra_state_attributes", None)
                        or self._attr_extra_state_attributes == {}
                    ) and self._config.get(CONF_ATTRIBUTES):
                        self._attr_extra_state_attributes = self._update_attr_settings(
                            self._config.get(CONF_ATTRIBUTES)
                        )
                        _LOGGER.debug(
                            "(%s) [restored] applied config attributes: %s",
                            self._attr_name,
                            self._attr_extra_state_attributes,
                        )
                        try:
                            self.async_write_ha_state()
                        except RuntimeError as err:
                            _LOGGER.debug(
                                "(%s) async_write_ha_state failed during restore: %s",
                                self._attr_name,
                                err,
                            )
        if self._config.get(CONF_UPDATED, True):
            self._config.update({CONF_UPDATED: False})
            self._hass.config_entries.async_update_entry(
                self._config_entry,
                data=self._config,
                options={},
            )
            _LOGGER.debug(
                "(%s) Updated config_updated: %s",
                self._attr_name,
                self._config_entry.data.get(CONF_UPDATED),
            )

    def _update_attr_settings(self, new_attributes: Any = None, just_pop: bool = False) -> Any:
        """Apply special entity settings and return unconsumed attributes.

        Args:
            new_attributes: Dynamic attribute payload to process.
            just_pop: Remove special attributes without applying their values.

        Returns:
            A copy of the remaining attributes, the unsupported input unchanged,
            or ``None`` when no attributes were provided.
        """
        if new_attributes is not None:
            _LOGGER.debug(
                "(%s) [update_attr_settings] Updating Special Attributes", self._attr_name
            )
            if isinstance(new_attributes, MutableMapping):
                attributes = copy.deepcopy(new_attributes)
                for attrib, setting in VARIABLE_ATTR_SETTINGS.items():
                    if attrib in attributes:
                        if just_pop:
                            attributes.pop(attrib, None)
                        else:
                            value = attributes.pop(attrib, None)
                            if attrib == ATTR_LOCATION_NAME:
                                self._set_location_name(value)
                            else:
                                setattr(self, setting, value)
                return copy.deepcopy(attributes)
            _LOGGER.error(
                "(%s) AttributeError: Attributes must be a dictionary: %s",
                self._attr_name,
                new_attributes,
            )
            return new_attributes
        return None

    def _set_location_name(self, location_name: str | None) -> None:
        """Store free-form location context and support pre-2026.6 state behavior.

        Home Assistant 2026.6 introduced ``TrackerEntity.in_zones`` for tracker
        state calculation. Until the integration minimum version is 2026.6 or
        newer, older cores need ``_attr_location_name`` to retain their legacy
        location-name state. Newer cores keep the name as an extra attribute.
        """
        self._location_name = location_name
        if not SUPPORTS_TRACKER_IN_ZONES:
            self._attr_location_name = location_name

    async def async_update_variable(self, **kwargs) -> None:
        """Update Device Tracker Variable."""
        _LOGGER.debug("(%s) [async_update_variable] kwargs: %s", self._attr_name, kwargs)

        updated_attributes = None

        replace_attributes = kwargs.get(ATTR_REPLACE_ATTRIBUTES, False)
        _LOGGER.debug(
            "(%s) [async_update_variable] Replace Attributes: %s",
            self._attr_name,
            replace_attributes,
        )

        if (
            not replace_attributes
            and hasattr(self, "_attr_extra_state_attributes")
            and self._attr_extra_state_attributes is not None
        ):
            updated_attributes = copy.deepcopy(self._attr_extra_state_attributes)

        attributes = kwargs.get(ATTR_ATTRIBUTES)
        if attributes is not None:
            if isinstance(attributes, str):
                try:
                    attributes = yaml.safe_load(attributes)
                except yaml.YAMLError as err:
                    _LOGGER.error(
                        "(%s) Failed to parse attributes string: %s", self._attr_name, err
                    )
                    attributes = None
            if isinstance(attributes, MutableMapping):
                _LOGGER.debug(
                    "(%s) [async_update_variable] New Attributes: %s",
                    self._attr_name,
                    attributes,
                )
                extra_attributes = self._update_attr_settings(attributes)
                if extra_attributes is not None:
                    try:
                        updated_attributes = merge_attribute_dict(
                            updated_attributes, extra_attributes
                        )
                    except ValueError as err:
                        _LOGGER.error(
                            "(%s) AttributeError: %s",
                            self._attr_name,
                            err,
                        )
            else:
                _LOGGER.error(
                    "(%s) AttributeError: Attributes must be a dictionary: %s",
                    self._attr_name,
                    attributes,
                )

        if updated_attributes is not None:
            self._attr_extra_state_attributes = copy.deepcopy(updated_attributes)
            _LOGGER.debug(
                "(%s) [async_update_variable] Final Attributes: %s",
                self._attr_name,
                updated_attributes,
            )
        else:
            self._attr_extra_state_attributes = {}

        if ATTR_LATITUDE in kwargs:
            self._attr_latitude = kwargs.get(ATTR_LATITUDE)
        if ATTR_LONGITUDE in kwargs:
            self._attr_longitude = kwargs.get(ATTR_LONGITUDE)
        if ATTR_IN_ZONES in kwargs:
            self._attr_in_zones = kwargs.get(ATTR_IN_ZONES)
        if ATTR_DELETE_IN_ZONES in kwargs and kwargs.get(ATTR_DELETE_IN_ZONES) is True:
            self._attr_in_zones = None
        if ATTR_LOCATION_NAME in kwargs:
            self._set_location_name(kwargs.get(ATTR_LOCATION_NAME))
        if ATTR_BATTERY_LEVEL in kwargs:
            self._attr_battery_level = kwargs.get(ATTR_BATTERY_LEVEL)
        if ATTR_GPS_ACCURACY in kwargs:
            self._attr_gps_accuracy = kwargs.get(ATTR_GPS_ACCURACY)
        if ATTR_DELETE_LOCATION_NAME in kwargs and kwargs.get(ATTR_DELETE_LOCATION_NAME) is True:
            self._set_location_name(None)
        try:
            self.async_write_ha_state()
        except RuntimeError as err:
            _LOGGER.debug(
                "(%s) async_write_ha_state failed during update: %s", self._attr_name, err
            )

    @property
    def force_update(self) -> bool:
        """Force update status of the entity."""
        return bool(self._force_update)

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return self._attr_gps_accuracy if self._attr_gps_accuracy is not None else 0

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return custom device-tracker state attributes."""
        attr = dict(self._attr_extra_state_attributes or {})
        if self._attr_source_type is not None:
            attr[ATTR_SOURCE_TYPE] = self._attr_source_type
        if self._attr_battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self._attr_battery_level
        if self._location_name is not None:
            attr[ATTR_LOCATION_NAME] = self._location_name
        return attr


class VariableNoRecorder(Variable):
    """Device tracker variable excluded from recorder history."""

    _unrecorded_attributes = frozenset({MATCH_ALL})

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Exclude from recorder automatically
        await _async_exclude_entity_from_recorder(self.hass, self.entity_id)

        _LOGGER.debug("(%s) Excluded from recorder: %s", self._attr_name, self.entity_id)
