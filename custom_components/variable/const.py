from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform
from homeassistant.helpers import selector

# sensor: SensorDeviceClass, DEVICE_CLASS_STATE_CLASSES, DEVICE_CLASS_UNITS
# binary_sensor: BinarySensorDeviceClass

DOMAIN = "variable"

PLATFORMS: list[str] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Defaults
DEFAULT_FORCE_UPDATE = False
DEFAULT_ICON = "mdi:variable"
DEFAULT_REPLACE_ATTRIBUTES = False
DEFAULT_RESTORE = True

CONF_ATTRIBUTES = "attributes"
CONF_ENTITY_PLATFORM = "entity_platform"
CONF_FORCE_UPDATE = "force_update"
CONF_RESTORE = "restore"
CONF_VALUE = "value"
CONF_VARIABLE_ID = "variable_id"

ATTR_ATTRIBUTES = "attributes"
ATTR_ENTITY = "entity"
ATTR_REPLACE_ATTRIBUTES = "replace_attributes"
ATTR_VALUE = "value"
ATTR_VARIABLE = "variable"

SENSOR_DEVICE_CLASS_SELECT_LIST = []
SENSOR_DEVICE_CLASS_SELECT_LIST.append(
    selector.SelectOptionDict(label="None", value="None")
)
for el in SensorDeviceClass:
    SENSOR_DEVICE_CLASS_SELECT_LIST.append(
        selector.SelectOptionDict(label=str(el.name), value=str(el.value))
    )

BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST = []
BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST.append(
    selector.SelectOptionDict(label="None", value="None")
)
for el in BinarySensorDeviceClass:
    BINARY_SENSOR_DEVICE_CLASS_SELECT_LIST.append(
        selector.SelectOptionDict(label=str(el.name), value=str(el.value))
    )
