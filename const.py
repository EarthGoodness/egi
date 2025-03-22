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
MODE_DRY = 0x02   # dehumidification
MODE_FAN = 0x04   # fan-only (air supply)
MODE_HEAT = 0x08
# (Other special modes exist but not directly exposed)

# VRF fan speed codes
FAN_AUTO = 0x00
FAN_LOW = 0x04
FAN_MEDIUM = 0x02
FAN_HIGH = 0x01

# Register base addresses and lengths
STATUS_BASE_ADDR = 0          # Starting register address for status blocks (D0000)
STATUS_REG_COUNT = 6          # Number of registers per indoor unit status block
CONTROL_BASE_ADDR = 4000      # Starting register address for control blocks (D4000)
CONTROL_REG_COUNT = 4         # Number of registers per indoor unit control block
