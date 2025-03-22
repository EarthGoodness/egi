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
BRAND_REG_STRIDE = 5  # Each IDU's brand data takes 5 registers: 8000–8004

# Optional: VRF brand code mapping for human-friendly logs
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
    0xFF: "Simulator"
}
