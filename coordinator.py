"""Data update coordinator for EGI VRF integration."""
import logging
from datetime import timedelta
from typing import Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STATUS_REG_COUNT

_LOGGER = logging.getLogger(__name__)

class EgiVrfCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data polling for EGI VRF indoor units."""

    def __init__(self, hass: HomeAssistant, client, update_interval: int):
        """Initialize the coordinator."""
        self.client = client  # EgiVrfModbusClient instance
        self.units = []       # list of active IDU indices currently present
        self.unit_info: Dict[int, dict] = {}  # static info per unit (brand, supported features, etc)
        interval = timedelta(seconds=update_interval)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} Data Coordinator", update_interval=interval)
        self.entry_id = None  # will be set by integration setup

    def set_initial_units(self, units: Dict[int, dict]):
        """Set initial discovered units and their info."""
        self.units = list(units.keys())
        self.unit_info = units
        # Initialize data dict for each unit (populated on first refresh)
        initial_data = {uid: {} for uid in self.units}
        self.data = initial_data

    async def _async_update_data(self):
        """Fetch data from the Modbus device for all known units."""
        data = {}
        if not self.units:
            return data  # no units to poll
        for uid in list(self.units):
            addr = uid * STATUS_REG_COUNT  # base address for this unit's status block
            regs = await self.hass.async_add_executor_job(self.client.read_holding_registers, addr, STATUS_REG_COUNT)
            if regs is None:
                raise UpdateFailed(f"Failed to read status registers for unit {uid}")
            regs = (regs + [0] * STATUS_REG_COUNT)[:STATUS_REG_COUNT]  # ensure list length
            power_val = regs[0] & 0xFF
            power_on = True if power_val == 1 else False
            mode_val = regs[1] & 0xFF
            fan_val = regs[3] & 0xFF
            setpoint_val = regs[4] & 0xFF
            room_temp = None
            fault_code = None
            if STATUS_REG_COUNT >= 6:
                combined = regs[5]
                room_temp = (combined >> 8) & 0xFF
                fault_code = combined & 0xFF
                # If values seem swapped, correct them
                if room_temp is not None and fault_code is not None and room_temp > 50 and fault_code < 50:
                    room_temp, fault_code = fault_code, room_temp
            data[uid] = {
                "power": power_on,
                "mode": mode_val,
                "fan": fan_val,
                "setpoint": setpoint_val,
                "room_temp": room_temp,
                "fault_code": fault_code
            }
        return data

    async def async_scan_idus(self):
        """Scan for indoor units and update the internal unit list and info. Returns True if successful."""
        results = await self.hass.async_add_executor_job(self.client.scan_idus)
        if results is None:
            # scanning failed (communication issue)
            return False
        current_set = set(self.units)
        new_set = set(results.keys())
        removed = current_set - new_set
        added = new_set - current_set

        # Update unit_info for all found units
        for uid, info in results.items():
            self.unit_info[uid] = info
        # Handle removed units
        for uid in removed:
            if uid in self.units:
                self.units.remove(uid)
                _LOGGER.info("Indoor unit %d is no longer present.", uid)
        # Handle added units (new or reappeared)
        for uid in added:
            if uid in self.unit_info and uid in current_set:
                # Reappeared unit (was known, likely entity exists)
                _LOGGER.info("Indoor unit %d reappeared.", uid)
                if uid not in self.units:
                    self.units.append(uid)
            else:
                # Brand new unit
                _LOGGER.info("Discovered new indoor unit %d (brand code %s).", uid, results[uid].get("brand_code"))
                self.units.append(uid)
                # Notify to add a new device/entity
                if self.entry_id:
                    from homeassistant.helpers.dispatcher import async_dispatcher_send
                    async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry_id}_new_device", uid, results[uid])
        # Read initial status for any added units (including reappeared) to update data
        for uid in added:
            regs = await self.hass.async_add_executor_job(self.client.read_holding_registers, uid * STATUS_REG_COUNT, STATUS_REG_COUNT)
            if regs is None:
                _LOGGER.warning("Could not read initial status for newly added unit %d", uid)
                continue
            regs = (regs + [0] * STATUS_REG_COUNT)[:STATUS_REG_COUNT]
            power_val = regs[0] & 0xFF
            power_on = True if power_val == 1 else False
            mode_val = regs[1] & 0xFF
            fan_val = regs[3] & 0xFF
            setpoint_val = regs[4] & 0xFF
            room_temp = None
            fault_code = None
            if STATUS_REG_COUNT >= 6:
                combined = regs[5]
                room_temp = (combined >> 8) & 0xFF
                fault_code = combined & 0xFF
                if room_temp is not None and fault_code is not None and room_temp > 50 and fault_code < 50:
                    room_temp, fault_code = fault_code, room_temp
            if self.data is None:
                self.data = {}
            self.data[uid] = {
                "power": power_on,
                "mode": mode_val,
                "fan": fan_val,
                "setpoint": setpoint_val,
                "room_temp": room_temp,
                "fault_code": fault_code
            }
        # Push updated data to listeners (entities)
        self.async_set_updated_data(self.data)
        return True
