# EGI VRF & HVAC Integration for Home Assistant

![HACS badge](https://img.shields.io/badge/HACS-Default-orange.svg)
![GitHub release](https://img.shields.io/github/v/release/EarthGoodness/egi)
![GitHub stars](https://img.shields.io/github/stars/EarthGoodness/egi?style=social)
[![Validate with HACS Action](https://github.com/EarthGoodness/egi/actions/workflows/validate.yml/badge.svg)](https://github.com/EarthGoodness/egi/actions/workflows/validate.yml)
[![Validate with hassfest Action](https://github.com/EarthGoodness/egi/actions/workflows/hassfest.yml/badge.svg)](https://github.com/EarthGoodness/egi/actions/workflows/hassfest.yml)

Seamless control of **EGI Modbus‑based HVAC adapters** directly from Home Assistant.

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

---

## Installation (HACS)

1. In Home Assistant go to **Settings → Add‑ons, Backups & Supervisor → Integrations → HACS**  
2. **Custom Repositories → +** and enter  
   `https://github.com/EarthGoodness/egi`  
   Category = **Integration**
3. Search for **“EGI VRF Gateway”** and click **Install**
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

