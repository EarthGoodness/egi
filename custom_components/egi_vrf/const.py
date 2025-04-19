"""Constants for EGI VRF integration."""
DOMAIN = "egi_vrf"

# Default serial connection parameters
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "E"  # Even parity
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_SLAVE_ID = 1

# Modbus function codes (for reference)
FUNC_READ_HOLDING = 0x03
FUNC_WRITE_SINGLE = 0x06
FUNC_WRITE_MULTIPLE = 0x10

# VRF mode codes (for writing)
MODE_COOL = 0x01
MODE_DRY = 0x02
MODE_FAN = 0x04
MODE_HEAT = 0x08

# VRF fan speed codes
FAN_AUTO = 0x00
FAN_LOW = 0x04
FAN_MEDIUM = 0x02
FAN_HIGH = 0x01

# Swing mode codes explicitly defined for Modbus and HA integration
SWING_OFF = 0x01
SWING_ON = 0x00

# HA to Modbus swing mode mapping (explicit)
SWING_MODE_HA_TO_MODBUS = {
    "off": 0x01,  # position 1
    "on": 0x00,   # swing
}

# Modbus to HA swing mode mapping explicitly required by climate.py
SWING_MODBUS_TO_HA = {
    0x00: "on",        # explicitly swing mode
    0x01: "off",         # fixed default position (position 1)
    0x02: "position 2",
    0x03: "position 3",
    0x04: "position 4",
    0x05: "position 5",
    0x06: "position 6",
}

# Register base addresses and lengths
STATUS_BASE_ADDR = 0
STATUS_REG_COUNT = 6
CONTROL_BASE_ADDR = 4000
CONTROL_REG_COUNT = 4
BRAND_REG_STRIDE = 5

# VRF adapter global info registers
ADAPTER_INFO_ADDR = 8000
ADAPTER_INFO_REG_COUNT = 5

OFFSET_BRAND_CODE = 0
OFFSET_SUPPORTED_MODES = 1
OFFSET_SUPPORTED_FAN = 2
OFFSET_TEMP_LIMITS = 3
OFFSET_SPECIAL_INFO = 4

SUPPORTED_MODES = {
    0x01: "Cool",
    0x02: "Dry",
    0x04: "Fan",
    0x08: "Heat"
}

SUPPORTED_FAN_SPEEDS = {
    0x01: "High",
    0x02: "Medium",
    0x04: "Low",
    0x20: "Auto"
}

def decode_temperature_limits(raw_limits):
    min_temp = (raw_limits & 0xFF00) >> 8
    max_temp = raw_limits & 0x00FF
    return {"min_temp": min_temp, "max_temp": max_temp}

SPECIAL_INFO_FLAGS = {
    0x01: "Master-slave concept",
    0x04: "Front and rear wind direction setting",
    0x08: "Left and right wind direction setting",
}

def decode_special_info(raw_special):
    flags = [name for bit, name in SPECIAL_INFO_FLAGS.items() if raw_special & bit]
    return flags if flags else ["No special features"]

BRAND_NAMES = {
    0x01: "Hitachi",
    0x02: "Daikin",
    0x03: "Toshiba",
    0x04: "Mitsubishi Heavy",
    0x05: "Mitsubishi",
    0x06: "Gree",
    0x07: "Hisense",
    0x08: "Midea",
    0x09: "Haier",
    0x0A: "LG",
    0x0B: "Default",
    0x0C: "Default",
    0x0D: "Samsung",
    0x0E: "AUX",
    0x0F: "Matsushita",
    0x10: "York",
    0x15: "McQuay",
    0x18: "TCL",
    0x1A: "Tianjia",
    0x23: "York Water",
    0x24: "Cool Wind",
    0x25: "Qingdao York",
    0x26: "Fujitsu",
    0x65: "Emerson Water",
    0x66: "McQuay Water",
    0x7E: "Toshiba",
    0xFF: "Simulator"
}
