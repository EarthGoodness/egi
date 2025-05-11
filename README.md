# EGI VRF & HVAC Integration for Home Assistant

![HACS badge](https://img.shields.io/badge/HACS-Default-orange.svg)
![GitHub release](https://img.shields.io/github/v/release/EarthGoodness/egi)
![GitHub stars](https://img.shields.io/github/stars/EarthGoodness/egi?style=social)
[![Validate with HACS Action](https://github.com/EarthGoodness/egi/actions/workflows/validate.yml/badge.svg)](https://github.com/EarthGoodness/egi/actions/workflows/validate.yml)
[![Validate with hassfest Action](https://github.com/EarthGoodness/egi/actions/workflows/hassfest.yml/badge.svg)](https://github.com/EarthGoodness/egi/actions/workflows/hassfest.yml)
[![Test Coverage](https://img.shields.io/codecov/c/github/EarthGoodness/egi?style=flat-square)](https://codecov.io/gh/EarthGoodness/egi)

Seamless control of **EGI HVAC & VRF adapters** directly from Home Assistant.

| Adapter | Max IDUs | Protocols | Features |
|---------|----------|-----------|----------|
| **EGI VRF Adapter Light** | 32 | RS‑485 Modbus RTU | Power, mode, temp, fan, swing |
| **EGI VRF Adapter Pro** | 64 | RTU / TCP | All Light features + brand selection, restart, time‑sync, locks, humidity |
| **EGI HVAC Adapter Solo** | 1 | RS‑485 Modbus RTU | Single‑IDU control, restart, brand write |

---

## Features

* **Climate entities** with full HVAC modes, target temperature, fan & swing
* **Gateway sensor** exposing brand, supported modes/limits, special flags
* **Select entity** to change adapter brand (Pro/Solo)
* **Service calls**  
  - `egi.set_brand_code`  
  - `egi.set_system_time`  
  - `egi.scan_idus`
* **Buttons** for on‑demand rescan, restart, factory‑reset (where supported)
* Supports both **serial (USB/RS‑485)** and **Modbus TCP**
* **Timing sensors**: 
  - `sensor.egi_adapter_<type>_setup_time` → seconds to complete adapter setup
  - `sensor.egi_adapter_<type>_poll_duration` → seconds per polling cycle

---

## Installation (HACS)

1. In Home Assistant go to **Settings → Add‑ons, Backups & Supervisor → Integrations → HACS**  
2. **Custom Repositories → +** and enter  
   `https://github.com/EarthGoodness/egi`  
   Category = **Integration**
3. Search for **“EGI”** and click **Install**
4. Restart Home Assistant when prompted.

---

## Configuration

1. **Settings → Devices & Services → + Add Integration → “EGI VRF Gateway”.**  
2. Select **Adapter type** (`solo`, `light`, `pro`) and **connection type**:  
   *Serial* → choose port, baud 9600 E 8 1 by default.  
   *TCP* → host, port 502.
3. Finish the wizard – indoor units are auto‑discovered and appear as **climate** devices.
4. *(Pro/Solo)*  Use the **Brand Select** dropdown or call  
   ```yaml
   service: egi.set_brand_code
   data:
     entry_id: <config_entry_id>
     brand_code: 6        # Gree
   ```

---

## Services

| Service | Description |
|---------|-------------|
| `egi.scan_idus` | Rescan gateway for newly‑added indoor units |
| `egi.set_system_time` | Sync adapter RTC with HA time |
| `egi.set_brand_code` | Write brand code and auto‑restart adapter |
| `egi.set_log_level` | Dynamically adjust logging level (`level: debug`, `info`, `warning`, `error`) |
---

## Logging & Diagnostics

The integration supports fine-grained logging by component. Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.egi: info
    custom_components.egi.modbus_client: debug
    custom_components.egi.adapter.AdapterSolo: debug
    custom_components.egi.adapter.AdapterVrfLight: debug
    custom_components.egi.adapter.AdapterVrfPro: debug
    custom_components.egi.climate: debug
    custom_components.egi.sensor: debug
    custom_components.egi.select: debug
    custom_components.egi.button: debug
```

You can also monitor performance:

- Setup duration is exposed as `sensor.egi_adapter_<type>_setup_time`
- Polling duration is tracked as `sensor.egi_adapter_<type>_poll_duration`

Example log:
```
[custom_components.egi.coordinator] Completed full data update for 2 devices in 0.63 seconds
```


## Usage Tips & Analytics

You can visualize or automate based on performance data from the timing sensors:

### Example Lovelace Card:
```yaml
type: entities
title: Adapter Performance
entities:
  - sensor.egi_adapter_solo_setup_time
  - sensor.egi_adapter_solo_poll_duration
  - sensor.egi_adapter_pro_poll_duration
```

### Use With InfluxDB + Grafana

1. Install the [InfluxDB integration](https://www.home-assistant.io/integrations/influxdb/)
2. Configure `configuration.yaml`:
```yaml
influxdb:
  include:
    entities:
      - sensor.egi_adapter_solo_poll_duration
      - sensor.egi_adapter_light_setup_time
```
3. Use Grafana to chart response times or trigger alerts if polling exceeds expected thresholds.

---

## Development & Contributing

Pull requests are welcome!

* Fork **[EarthGoodness/egi](https://github.com/EarthGoodness/egi)** and branch from **main**
* Pre‑commit linting: **ruff**, **black**, **flake8**
* Unit tests: **pytest**.

For the official Home‑Assistant submission see the **`core/`** folder (separate Git repo).

---

## Changelog

See the [release page](https://github.com/EarthGoodness/egi/releases).
