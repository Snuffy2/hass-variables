from __future__ import annotations

from enum import Enum
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components import binary_sensor, sensor
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from iso4217 import Currency
import voluptuous as vol

from .const import (
    CONF_ATTRIBUTES,
    CONF_ENTITY_PLATFORM,
    CONF_EXCLUDE_FROM_RECORDER,
    CONF_FORCE_UPDATE,
    CONF_RESTORE,
    CONF_UPDATED,
    CONF_VALUE,
    CONF_VALUE_TYPE,
    CONF_VARIABLE_ID,
    CONF_YAML_VARIABLE,
    DEFAULT_EXCLUDE_FROM_RECORDER,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_ICON,
    DEFAULT_RESTORE,
    DOMAIN,
    PLATFORMS,
)
from .helpers import value_to_type

_LOGGER = logging.getLogger(__name__)

COMPONENT_CONFIG_URL = "https://github.com/Wibias/hass-variables"

# Note the input displayed to the user will be translated. See the
# translations/<lang>.json file and strings.json. See here for further information:
# https://developers.home-assistant.io/docs/config_entries_config_flow_handler/#translations

SENSOR_DEVICE_CLASS_SELECT_LIST = []
SENSOR_DEVICE_CLASS_SELECT_LIST.append(
    selector.SelectOptionDict(label="None", value="None")
)
for el in sensor.SensorDeviceClass:
    if el != sensor.SensorDeviceClass.ENUM:
        SENSOR_DEVICE_CLASS_SELECT_LIST.append(
            selector.SelectOptionDict(label=str(el.name), value=str(el.value))
        )

BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST = []
BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST.append(
    selector.SelectOptionDict(label="None", value="None")
)
for el in binary_sensor.BinarySensorDeviceClass:
    BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST.append(
        selector.SelectOptionDict(label=str(el.name), value=str(el.value))
    )

ADD_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VARIABLE_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ICON, default=DEFAULT_ICON): selector.IconSelector(
            selector.IconSelectorConfig()
        ),
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SENSOR_DEVICE_CLASS_SELECT_LIST,
                multiple=False,
                custom_value=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_RESTORE, default=DEFAULT_RESTORE): selector.BooleanSelector(
            selector.BooleanSelectorConfig()
        ),
        vol.Optional(
            CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        vol.Optional(
            CONF_EXCLUDE_FROM_RECORDER, default=DEFAULT_EXCLUDE_FROM_RECORDER
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
    }
)

ADD_BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VARIABLE_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ICON, default=DEFAULT_ICON): selector.IconSelector(
            selector.IconSelectorConfig()
        ),
        vol.Optional(CONF_VALUE, default="None"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["None", "true", "false"],
                translation_key="boolean_options",
                multiple=False,
                custom_value=False,
                mode=selector.SelectSelectorMode.LIST,
            )
        ),
        vol.Optional(CONF_ATTRIBUTES): selector.ObjectSelector(
            selector.ObjectSelectorConfig()
        ),
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST,
                multiple=False,
                custom_value=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_RESTORE, default=DEFAULT_RESTORE): selector.BooleanSelector(
            selector.BooleanSelectorConfig()
        ),
        vol.Optional(
            CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        vol.Optional(
            CONF_EXCLUDE_FROM_RECORDER, default=DEFAULT_EXCLUDE_FROM_RECORDER
        ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
    }
)


async def validate_sensor_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input"""

    # _LOGGER.debug(f"[config_flow validate_sensor_input] data: {data}")
    if data.get(CONF_NAME):
        return {"title": data.get(CONF_NAME)}
    else:
        return {"title": data.get(CONF_VARIABLE_ID, "")}


class VariableConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    # Connection classes in homeassistant/config_entries.py are now deprecated

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["add_" + p for p in PLATFORMS],
        )

    async def async_step_add_sensor(
        self, user_input=None, errors=None, yaml_variable=False
    ):
        if user_input is not None:
            user_input.update({CONF_ENTITY_PLATFORM: Platform.SENSOR})
            user_input.update({CONF_YAML_VARIABLE: yaml_variable})
            _LOGGER.debug(f"[New Sensor Variable] page_1_input: {user_input}")
            self.add_sensor_input = user_input
            return await self.async_step_sensor_page_2()

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="add_sensor",
            data_schema=ADD_SENSOR_SCHEMA,
            errors=errors,
            description_placeholders={
                "component_config_url": COMPONENT_CONFIG_URL,
            },
        )

    async def async_step_sensor_page_2(self, user_input=None):
        errors = {}
        if user_input is not None:
            _LOGGER.debug(f"[New Sensor Page 2] page_1_input: {self.add_sensor_input}")
            _LOGGER.debug(f"[New Sensor Page 2] page_2_input: {user_input}")

            try:
                newval = value_to_type(
                    user_input.get(CONF_VALUE),
                    self.add_sensor_input.get(CONF_VALUE_TYPE),
                )
            except ValueError:
                errors["base"] = "invalid_value_type"
            else:
                user_input[CONF_VALUE] = newval

            if not errors:
                if self.add_sensor_input is not None and self.add_sensor_input:
                    user_input.update(self.add_sensor_input)
                if user_input is not None:
                    for k, v in list(user_input.items()):
                        if v is None or (isinstance(v, str) and v.lower() == "none"):
                            user_input.pop(k, None)
                _LOGGER.debug(f"[New Sensor Page 2] Final user_input: {user_input}")
                info = await validate_sensor_input(self.hass, user_input)
                return self.async_create_entry(
                    title=info.get("title", ""), data=user_input
                )

        _LOGGER.debug(f"[New Sensor Page 2] Initial user_input: {user_input}")
        # _LOGGER.debug(
        #    f"[New Sensor Page 2] device_class: {self.add_sensor_input.get(CONF_DEVICE_CLASS)}"
        # )

        SENSOR_PAGE_2_SCHEMA = self.build_add_sensor_page_2()

        if self.add_sensor_input.get(CONF_NAME) is None or self.add_sensor_input.get(
            CONF_NAME
        ) == self.add_sensor_input.get(CONF_VARIABLE_ID):
            disp_name = self.add_sensor_input.get(CONF_VARIABLE_ID)
        else:
            disp_name = f"{self.add_sensor_input.get(CONF_NAME)} ({self.add_sensor_input.get(CONF_VARIABLE_ID)})"
        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="sensor_page_2",
            data_schema=SENSOR_PAGE_2_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_class": self.add_sensor_input.get(CONF_DEVICE_CLASS, "None"),
                "disp_name": disp_name,
                "value_type": self.add_sensor_input.get(CONF_VALUE_TYPE, "None"),
            },
        )

    def build_add_sensor_page_2(self):
        SENSOR_STATE_CLASS_SELECT_LIST = []
        SENSOR_STATE_CLASS_SELECT_LIST.append(
            selector.SelectOptionDict(label="None", value="None")
        )
        SENSOR_UNITS_SELECT_LIST = []
        SENSOR_UNITS_SELECT_LIST.append(
            selector.SelectOptionDict(label="None", value="None")
        )

        SENSOR_PAGE_2_SCHEMA = vol.Schema({})
        if (
            self.add_sensor_input.get(CONF_DEVICE_CLASS) is not None
            and self.add_sensor_input.get(CONF_DEVICE_CLASS).lower() != "none"
        ):
            for el in sensor.DEVICE_CLASS_STATE_CLASSES.get(
                self.add_sensor_input.get(CONF_DEVICE_CLASS), Enum
            ):
                SENSOR_STATE_CLASS_SELECT_LIST.append(
                    selector.SelectOptionDict(label=str(el.name), value=str(el.value))
                )
            if (
                self.add_sensor_input.get(CONF_DEVICE_CLASS)
                == sensor.SensorDeviceClass.MONETARY
            ):
                for el in Currency:
                    if el.code not in ["XTS", "XXX"]:
                        SENSOR_UNITS_SELECT_LIST.append(
                            selector.SelectOptionDict(
                                label=f"{el.currency_name} [{el.code}]",
                                value=str(el.code),
                            )
                        )
            else:
                for el in sensor.DEVICE_CLASS_UNITS.get(
                    self.add_sensor_input.get(CONF_DEVICE_CLASS), []
                ):
                    if el is not None and el != "None":
                        SENSOR_UNITS_SELECT_LIST.append(
                            selector.SelectOptionDict(label=str(el), value=str(el))
                        )
            if self.add_sensor_input.get(CONF_DEVICE_CLASS) in [
                sensor.SensorDeviceClass.DATE
            ]:
                SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                    {
                        vol.Optional(CONF_VALUE): selector.DateSelector(
                            selector.DateSelectorConfig()
                        )
                    }
                )
                value_type = "date"
            elif self.add_sensor_input.get(CONF_DEVICE_CLASS) in [
                sensor.SensorDeviceClass.TIMESTAMP
            ]:
                SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                    {
                        vol.Optional(CONF_VALUE): selector.DateTimeSelector(
                            selector.DateTimeSelectorConfig()
                        )
                    }
                )
                value_type = "datetime"
            else:
                SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                    {
                        vol.Optional(CONF_VALUE): selector.TextSelector(
                            selector.TextSelectorConfig()
                        )
                    }
                )
                value_type = "number"
        else:
            for el in sensor.SensorStateClass:
                SENSOR_STATE_CLASS_SELECT_LIST.append(
                    selector.SelectOptionDict(label=str(el.name), value=str(el.value))
                )

            SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                {
                    vol.Optional(CONF_VALUE): selector.TextSelector(
                        selector.TextSelectorConfig()
                    )
                }
            )
            value_type = "string"

        # _LOGGER.debug(
        #    f"[New Sensor Page 2] SENSOR_STATE_CLASS_SELECT_LIST: {SENSOR_STATE_CLASS_SELECT_LIST}"
        # )
        # _LOGGER.debug(
        #    f"[New Sensor Page 2] SENSOR_UNITS_SELECT_LIST: {SENSOR_UNITS_SELECT_LIST}"
        # )

        SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
            {
                vol.Optional(CONF_ATTRIBUTES): selector.ObjectSelector(
                    selector.ObjectSelectorConfig()
                )
            }
        )
        if len(SENSOR_STATE_CLASS_SELECT_LIST) > 1:
            SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                {
                    vol.Optional(sensor.CONF_STATE_CLASS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SENSOR_STATE_CLASS_SELECT_LIST,
                            multiple=False,
                            custom_value=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )

        if len(SENSOR_UNITS_SELECT_LIST) > 1:
            SENSOR_PAGE_2_SCHEMA = SENSOR_PAGE_2_SCHEMA.extend(
                {
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SENSOR_UNITS_SELECT_LIST,
                            multiple=False,
                            custom_value=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )

        # _LOGGER.debug(f"[New Sensor Page 2] value_type: {value_type}")
        self.add_sensor_input.update({CONF_VALUE_TYPE: value_type})
        return SENSOR_PAGE_2_SCHEMA

    async def async_step_add_binary_sensor(
        self, user_input=None, errors=None, yaml_variable=False
    ):
        if user_input is not None:

            try:
                user_input.update({CONF_ENTITY_PLATFORM: Platform.BINARY_SENSOR})
                user_input.update({CONF_YAML_VARIABLE: yaml_variable})
                info = await validate_sensor_input(self.hass, user_input)
                _LOGGER.debug(f"[New Binary Sensor] updated user_input: {user_input}")
                return self.async_create_entry(
                    title=info.get("title", ""), data=user_input
                )
            except Exception as err:
                _LOGGER.exception(
                    f"[config_flow async_step_add_binary_sensor] Unexpected exception: {err}"
                )
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="add_binary_sensor",
            data_schema=ADD_BINARY_SENSOR_SCHEMA,
            errors=errors,
            description_placeholders={
                "component_config_url": COMPONENT_CONFIG_URL,
            },
        )

    # this is run to import the configuration.yaml parameters\
    async def async_step_import(self, import_config=None) -> FlowResult:
        """Import a config entry from configuration.yaml."""

        # _LOGGER.debug(f"[async_step_import] import_config: {import_config)}")
        return await self.async_step_add_sensor(
            user_input=import_config, yaml_variable=True
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ):
        """Get the options flow."""
        return VariableOptionsFlowHandler(config_entry)


class VariableOptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        # _LOGGER.debug("Starting Options")
        # _LOGGER.debug(f"[Options] initial config: {self.config_entry.data)}")
        # _LOGGER.debug(f"[Options] initial options: {self.config_entry.options)}")

        if not self.config_entry.data.get(CONF_YAML_VARIABLE):
            if self.config_entry.data.get(CONF_ENTITY_PLATFORM) in PLATFORMS and (
                new_func := getattr(
                    self,
                    "async_step_"
                    + self.config_entry.data.get(CONF_ENTITY_PLATFORM)
                    + "_options",
                    False,
                )
            ):
                return await new_func()
        else:
            _LOGGER.debug("No Options for YAML Created Variables")
            return self.async_abort(reason="yaml_variable")

    async def async_step_sensor_options(
        self, user_input=None, errors=None
    ) -> FlowResult:

        if user_input is not None:
            _LOGGER.debug(f"[Sensor Options Page 1] page_1_input: {user_input}")
            self.sensor_options_page_1 = user_input
            return await self.async_step_sensor_options_page_2()

        SENSOR_OPTIONS_PAGE_1_SCHEMA = self.build_sensor_options_page_1()

        if self.config_entry.data.get(CONF_NAME) is None or self.config_entry.data.get(
            CONF_NAME
        ) == self.config_entry.data.get(CONF_VARIABLE_ID):
            disp_name = self.config_entry.data.get(CONF_VARIABLE_ID)
        else:
            disp_name = f"{self.config_entry.data.get(CONF_NAME)} ({self.config_entry.data.get(CONF_VARIABLE_ID)})"

        return self.async_show_form(
            step_id="sensor_options",
            data_schema=SENSOR_OPTIONS_PAGE_1_SCHEMA,
            errors=errors,
            description_placeholders={
                "component_config_url": COMPONENT_CONFIG_URL,
                "disp_name": disp_name,
            },
        )

    def build_sensor_options_page_1(self):
        return vol.Schema(
            {
                vol.Optional(
                    CONF_DEVICE_CLASS,
                    default=self.config_entry.data.get(CONF_DEVICE_CLASS, "None"),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=SENSOR_DEVICE_CLASS_SELECT_LIST,
                        multiple=False,
                        custom_value=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_RESTORE,
                    default=self.config_entry.data.get(CONF_RESTORE, DEFAULT_RESTORE),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
                vol.Optional(
                    CONF_FORCE_UPDATE,
                    default=self.config_entry.data.get(
                        CONF_FORCE_UPDATE, DEFAULT_FORCE_UPDATE
                    ),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
                vol.Optional(
                    CONF_EXCLUDE_FROM_RECORDER,
                    default=self.config_entry.data.get(
                        CONF_EXCLUDE_FROM_RECORDER, DEFAULT_EXCLUDE_FROM_RECORDER
                    ),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            }
        )

    async def async_step_sensor_options_page_2(self, user_input=None):
        errors = {}
        if user_input is not None:
            _LOGGER.debug(f"[Sensor Options Page 2] user_input: {user_input}")
            try:
                newval = value_to_type(
                    user_input.get(CONF_VALUE),
                    self.sensor_options_page_1.get(CONF_VALUE_TYPE),
                )
            except ValueError:
                errors["base"] = "invalid_value_type"
            else:
                user_input[CONF_VALUE] = newval

            # _LOGGER.debug(
            #    f"[Sensor Options Page 2] value_type: {self.sensor_options_page_1.get(CONF_VALUE_TYPE)}"
            # )
            # _LOGGER.debug(
            #    f"[Sensor Options Page 2] type of value: {type(user_input.get(CONF_VALUE))}"
            # )

            if not errors:
                if (
                    self.sensor_options_page_1 is not None
                    and self.sensor_options_page_1
                ):
                    user_input.update(self.sensor_options_page_1)
                for m in dict(self.config_entry.data).keys():
                    user_input.setdefault(m, self.config_entry.data[m])
                if user_input is not None:
                    for k, v in list(user_input.items()):
                        if v is None or (isinstance(v, str) and v.lower() == "none"):
                            user_input.pop(k, None)
                user_input.update({CONF_UPDATED: True})
                _LOGGER.debug(f"[Sensor Options Page 2] Final user_input: {user_input}")
                self.config_entry.options = {}

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                    options=self.config_entry.options,
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data=user_input)

        _LOGGER.debug(f"[Sensor Options Page 2] Initial user_input: {user_input}")
        # _LOGGER.debug(
        #    f"[Sensor Options Page 2] device_class: {self.sensor_options_page_1.get(CONF_DEVICE_CLASS)}"
        # )

        SENSOR_OPTIONS_PAGE_2_SCHEMA = self.build_sensor_options_page_2()

        if self.config_entry.data.get(CONF_NAME) is None or self.config_entry.data.get(
            CONF_NAME
        ) == self.config_entry.data.get(CONF_VARIABLE_ID):
            disp_name = self.config_entry.data.get(CONF_VARIABLE_ID)
        else:
            disp_name = f"{self.config_entry.data.get(CONF_NAME)} ({self.config_entry.data.get(CONF_VARIABLE_ID)})"

        return self.async_show_form(
            step_id="sensor_options_page_2",
            data_schema=SENSOR_OPTIONS_PAGE_2_SCHEMA,
            errors=errors,
            description_placeholders={
                "disp_name": disp_name,
                "value_type": self.sensor_options_page_1.get(CONF_VALUE_TYPE, "None"),
                "device_class": self.sensor_options_page_1.get(
                    CONF_DEVICE_CLASS, "None"
                ),
            },
        )

    def check_value_default(self, new_device_class):
        val_default_value = None
        if self.config_entry.data.get(CONF_VALUE) is None or (
            isinstance(self.config_entry.data.get(CONF_VALUE), str)
            and self.config_entry.data.get(CONF_VALUE).lower() == "none"
        ):
            val_default = False
        elif self.config_entry.data.get(CONF_DEVICE_CLASS) != new_device_class:
            val_default = False
        else:
            val_default = True
            val_default_value = self.config_entry.data.get(CONF_VALUE)
        return val_default, val_default_value

    def build_sensor_options_page_2(self):
        SENSOR_STATE_CLASS_SELECT_LIST = []
        SENSOR_STATE_CLASS_SELECT_LIST.append(
            selector.SelectOptionDict(label="None", value="None")
        )
        SENSOR_UNITS_SELECT_LIST = []
        SENSOR_UNITS_SELECT_LIST.append(
            selector.SelectOptionDict(label="None", value="None")
        )

        val_default, val_default_value = self.check_value_default(
            self.sensor_options_page_1.get(CONF_DEVICE_CLASS)
        )

        SENSOR_OPTIONS_PAGE_2_SCHEMA = vol.Schema({})
        if (
            self.sensor_options_page_1.get(CONF_DEVICE_CLASS) is not None
            and self.sensor_options_page_1.get(CONF_DEVICE_CLASS).lower() != "none"
        ):
            for el in sensor.DEVICE_CLASS_STATE_CLASSES.get(
                self.sensor_options_page_1.get(CONF_DEVICE_CLASS), Enum
            ):
                SENSOR_STATE_CLASS_SELECT_LIST.append(
                    selector.SelectOptionDict(label=str(el.name), value=str(el.value))
                )
            if (
                self.sensor_options_page_1.get(CONF_DEVICE_CLASS)
                == sensor.SensorDeviceClass.MONETARY
            ):
                for el in Currency:
                    if el.code not in ["XTS", "XXX"]:
                        SENSOR_UNITS_SELECT_LIST.append(
                            selector.SelectOptionDict(
                                label=f"{el.currency_name} [{el.code}]",
                                value=str(el.code),
                            )
                        )
            else:
                for el in sensor.DEVICE_CLASS_UNITS.get(
                    self.sensor_options_page_1.get(CONF_DEVICE_CLASS), []
                ):
                    if el is not None and el != "None":
                        SENSOR_UNITS_SELECT_LIST.append(
                            selector.SelectOptionDict(label=str(el), value=str(el))
                        )

            if self.sensor_options_page_1.get(CONF_DEVICE_CLASS) in [
                sensor.SensorDeviceClass.DATE
            ]:
                value_type = "date"
                if val_default:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(
                                CONF_VALUE,
                                default=val_default_value,
                            ): selector.DateSelector(selector.DateSelectorConfig())
                        }
                    )
                else:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(
                                CONF_VALUE,
                            ): selector.DateSelector(selector.DateSelectorConfig())
                        }
                    )

            elif self.sensor_options_page_1.get(CONF_DEVICE_CLASS) in [
                sensor.SensorDeviceClass.TIMESTAMP
            ]:
                value_type = "datetime"
                if val_default:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(
                                CONF_VALUE,
                                default=val_default_value,
                            ): selector.DateTimeSelector(
                                selector.DateTimeSelectorConfig()
                            )
                        }
                    )
                else:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(CONF_VALUE,): selector.DateTimeSelector(
                                selector.DateTimeSelectorConfig()
                            )
                        }
                    )
            else:
                value_type = "number"
                if val_default:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(
                                CONF_VALUE,
                                default=str(val_default_value),
                            ): selector.TextSelector(selector.TextSelectorConfig())
                        }
                    )
                else:
                    SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                        {
                            vol.Optional(
                                CONF_VALUE,
                            ): selector.TextSelector(selector.TextSelectorConfig())
                        }
                    )
        else:
            for el in sensor.SensorStateClass:
                SENSOR_STATE_CLASS_SELECT_LIST.append(
                    selector.SelectOptionDict(label=str(el.name), value=str(el.value))
                )
            value_type = "string"
            if val_default:
                SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                    {
                        vol.Optional(
                            CONF_VALUE,
                            default=val_default_value,
                        ): selector.TextSelector(selector.TextSelectorConfig())
                    }
                )
            else:
                SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                    {
                        vol.Optional(
                            CONF_VALUE,
                        ): selector.TextSelector(selector.TextSelectorConfig())
                    }
                )

        # _LOGGER.debug(
        #    f"[Sensor Options Page 2] SENSOR_STATE_CLASS_SELECT_LIST: {SENSOR_STATE_CLASS_SELECT_LIST}"
        # )
        # _LOGGER.debug(
        #    f"[Sensor Options Page 2] SENSOR_UNITS_SELECT_LIST: {SENSOR_UNITS_SELECT_LIST}"
        # )

        SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
            {
                vol.Optional(
                    CONF_ATTRIBUTES, default=self.config_entry.data.get(CONF_ATTRIBUTES)
                ): selector.ObjectSelector(selector.ObjectSelectorConfig())
            }
        )
        if len(SENSOR_STATE_CLASS_SELECT_LIST) > 1:
            SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                {
                    vol.Optional(
                        sensor.CONF_STATE_CLASS,
                        default=self.config_entry.data.get(
                            sensor.CONF_STATE_CLASS, "None"
                        )
                        if (
                            self.config_entry.data.get(CONF_DEVICE_CLASS)
                            == self.sensor_options_page_1.get(CONF_DEVICE_CLASS)
                        )
                        else "None",
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SENSOR_STATE_CLASS_SELECT_LIST,
                            multiple=False,
                            custom_value=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )
        else:
            self.sensor_options_page_1[sensor.CONF_STATE_CLASS] = None

        if len(SENSOR_UNITS_SELECT_LIST) > 1:
            SENSOR_OPTIONS_PAGE_2_SCHEMA = SENSOR_OPTIONS_PAGE_2_SCHEMA.extend(
                {
                    vol.Optional(
                        CONF_UNIT_OF_MEASUREMENT,
                        default=self.config_entry.data.get(
                            CONF_UNIT_OF_MEASUREMENT, "None"
                        )
                        if (
                            self.config_entry.data.get(CONF_DEVICE_CLASS)
                            == self.sensor_options_page_1.get(CONF_DEVICE_CLASS)
                        )
                        else "None",
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SENSOR_UNITS_SELECT_LIST,
                            multiple=False,
                            custom_value=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )
        else:
            self.sensor_options_page_1[CONF_UNIT_OF_MEASUREMENT] = None

        # _LOGGER.debug(f"[Sensor Options Page 2] value_type: {value_type}")
        self.sensor_options_page_1.update({CONF_VALUE_TYPE: value_type})
        return SENSOR_OPTIONS_PAGE_2_SCHEMA

    async def async_step_binary_sensor_options(
        self, user_input=None, errors=None
    ) -> FlowResult:

        if user_input is not None:
            _LOGGER.debug(f"[Binary Sensor Options] user_input: {user_input}")
            for m in dict(self.config_entry.data).keys():
                user_input.setdefault(m, self.config_entry.data[m])
            user_input.update({CONF_UPDATED: True})
            _LOGGER.debug(f"[Binary Sensor Options] updated user_input: {user_input}")
            self.config_entry.options = {}

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input, options=self.config_entry.options
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        BINARY_SENSOR_OPTIONS_SCHEMA = vol.Schema(
            {
                vol.Optional(
                    CONF_VALUE,
                    default=self.config_entry.data.get(CONF_VALUE)
                    if self.config_entry.data.get(CONF_VALUE) is not None
                    else "None",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["None", "true", "false"],
                        translation_key="boolean_options",
                        multiple=False,
                        custom_value=False,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_ATTRIBUTES, default=self.config_entry.data.get(CONF_ATTRIBUTES)
                ): selector.ObjectSelector(selector.ObjectSelectorConfig()),
                vol.Optional(
                    CONF_DEVICE_CLASS,
                    default=self.config_entry.data.get(CONF_DEVICE_CLASS, "None"),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST,
                        multiple=False,
                        custom_value=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_RESTORE,
                    default=self.config_entry.data.get(CONF_RESTORE, DEFAULT_RESTORE),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
                vol.Optional(
                    CONF_FORCE_UPDATE,
                    default=self.config_entry.data.get(
                        CONF_FORCE_UPDATE, DEFAULT_FORCE_UPDATE
                    ),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
                vol.Optional(
                    CONF_EXCLUDE_FROM_RECORDER,
                    default=self.config_entry.data.get(
                        CONF_EXCLUDE_FROM_RECORDER, DEFAULT_EXCLUDE_FROM_RECORDER
                    ),
                ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            }
        )

        if self.config_entry.data.get(CONF_NAME) is None or self.config_entry.data.get(
            CONF_NAME
        ) == self.config_entry.data.get(CONF_VARIABLE_ID):
            disp_name = self.config_entry.data.get(CONF_VARIABLE_ID)
        else:
            disp_name = f"{self.config_entry.data.get(CONF_NAME)} ({self.config_entry.data.get(CONF_VARIABLE_ID)})"

        return self.async_show_form(
            step_id="binary_sensor_options",
            data_schema=BINARY_SENSOR_OPTIONS_SCHEMA,
            errors=errors,
            description_placeholders={
                "component_config_url": COMPONENT_CONFIG_URL,
                "disp_name": disp_name,
            },
        )
