"""Constants for the EGI VRF integration."""

DOMAIN = "egi_vrf"

# Configuration keys
CONF_PORT = "port"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stop_bits"
CONF_SLAVE_ID = "slave_address"
CONF_POLL_INTERVAL = "poll_interval"

# Default values
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "E"    # Even parity
DEFAULT_STOPBITS = 1
DEFAULT_SLAVE_ID = 1
DEFAULT_POLL_INTERVAL = 30  # seconds

# Modbus addresses constants
MAX_IDU_UNITS = 32
BASE_BRAND_ADDR = 8000  # base address for brand registers (D8000 in decimal notation)
BRAND_REG_STRIDE = 5      # each IDU performance info block size in registers
STATUS_REG_COUNT = 6      # number of registers per IDU status

# Home Assistant climate modes and fan speeds mapping
HVAC_MODE_OFF = "off"
HVAC_MODE_COOL = "cool"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_DRY = "dry"
HVAC_MODE_FAN_ONLY = "fan_only"
HVAC_MODE_AUTO = "auto"

FAN_MODE_AUTO = "auto"
FAN_MODE_LOW = "low"
FAN_MODE_MEDIUM = "medium"
FAN_MODE_HIGH = "high"
