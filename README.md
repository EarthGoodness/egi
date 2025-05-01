# EGI VRF & HVAC Integration for Home Assistant

![HACS badge](https://img.shields.io/badge/HACS-Default-orange.svg)
![GitHub release](https://img.shields.io/github/v/release/EarthGoodness/egi_zigbee)
![GitHub stars](https://img.shields.io/github/stars/EarthGoodness/egi_zigbee?style=social)
[![Validate with HACS Action](https://github.com/EarthGoodness/egi_zigbee/actions/workflows/validate.yml/badge.svg)](https://github.com/EarthGoodness/egi_zigbee/actions/workflows/hacs.yml)
[![Validate with hassfest Action](https://github.com/EarthGoodness/egi/actions/workflows/hassfest.yml/badge.svg)](https://github.com/EarthGoodness/egi_zigbee/actions/workflows/hassfest.yml)

# EGI Zigbee HVAC/VRF Adapter

Home Assistant integration for EGI Zigbee-based HVAC & VRF adapters, supporting multiple models (Solo, Light, Pro) simultaneously under ZHA.

## Features

- ClimateEntity for temperature and mode control  
- FanEntity for fan speed and on/off control  
- Automatic discovery via ZHA  
- Adapter-specific DP parsing via modular adapter classes  

## Installation

### HACS

1. In Home Assistant go to **HACS → Integrations → ⋯ (top right) → Custom repositories**.  
2. Add repository URL `https://github.com/EarthGoodness/egi_zigbee`, select **Integration**.  
3. Install **EGI Zigbee HVAC/VRF Adapter**.  
4. Restart Home Assistant.

### Manual

1. Clone this repo into your HA config’s `custom_components` folder:
   ```bash
   cd /config/custom_components
   git clone https://github.com/EarthGoodness/egi_zigbee.git egi_zigbee
