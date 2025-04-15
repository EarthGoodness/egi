# EGI VRF Modbus RTU Integration for Home Assistant

This custom integration connects EGI VRF Adapters (Light and Pro) via Modbus RTU/TCP to Home Assistant, exposing each indoor unit (IDU) as a climate entity with full control and status reporting.

## Features

- 🔥 Heating / ❄️ Cooling / 💧 Dry / 🌬️ Fan modes
- 🎛️ Fan speed control (auto, low, medium, high)
- 🔁 Swing control (vertical, horizontal, both)
- 🌪️ Wind direction (optional select entity)
- 🧠 Error and brand code monitoring
- 📡 Supports:
  - EGI VRF Adapter Light
  - EGI VRF Adapter Pro (AC200)
  - Single-IDU Modbus Adapters (1:1)
- 🧩 Configurable via UI (serial/TCP)
- 🛠️ Full rescan and dynamic device discovery

## Installation

1. Install via [HACS](https://hacs.xyz/):
   - Go to HACS → Integrations → 3-dot menu → Custom repositories
   - Add this repository URL
   - Category: Integration

2. Restart Home Assistant

3. Go to **Settings → Devices & Services → Add Integration** and search for `EGI VRF`.

## Configuration

You can configure:
- Connection type: Serial or TCP
- Serial port, baudrate, parity
- TCP host and port
- Slave ID
- Adapter type: Light, Pro, Single-IDU

All indoor units will be auto-discovered and created.

## Screenshots

📸 [Optional: add a screenshot of your dashboard]

## License

MIT © EGI Energy Solutions
