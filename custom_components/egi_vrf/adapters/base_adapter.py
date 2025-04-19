"""Base class for EGI VRF adapter profiles."""


class BaseAdapter:
    """
    Base interface for an EGI VRF adapter profile.
    Each subclass must implement the read/write methods according to its Modbus mapping.
    """

    def __init__(self):
        # Common flags or info; subclasses can override
        self.name = "BaseAdapter"
        self.max_idus = 1
        self.supports_brand_write = False

    def scan_devices(self, client):
        """
        Return a list of (system, index) or (address) for all discovered IDUs.
        Subclasses that support multiple IDUs should override.
        """
        # By default, assume single device only
        return [(0, 0)]

    def read_status(self, client, system, index):
        """
        Read status registers for the given IDU (system,index)
        Return a dict with keys like:
          {
            "available": bool,
            "power": bool,
            "mode_code": int,
            "target_temp": int,
            "current_temp": float,
            "fan_code": int,
            "wind_code": int,
            "error_code": int,
          }
        Subclass must implement.
        """
        raise NotImplementedError("read_status() must be implemented by subclass.")

    def write_power(self, client, system, index, power_on: bool):
        """Turn IDU on/off. Subclass must implement."""
        raise NotImplementedError("write_power() must be implemented by subclass.")

    def write_mode(self, client, system, index, mode_code: int):
        """Set mode (heat/cool/fan/dry). Subclass must implement."""
        raise NotImplementedError("write_mode() must be implemented by subclass.")

    def write_temperature(self, client, system, index, temp: int):
        """Set target temperature. Subclass must implement."""
        raise NotImplementedError("write_temperature() must be implemented by subclass.")

    def write_fan_speed(self, client, system, index, fan_code: int):
        """Set fan speed. Subclass must implement."""
        raise NotImplementedError("write_fan_speed() must be implemented by subclass.")

    def write_swing(self, client, system, index, swing_code: int):
        """Set swing/wind direction. Subclass must implement."""
        raise NotImplementedError("write_swing() must be implemented by subclass.")

    def read_brand_code(self, client):
        """Read global brand code from the adapter if available."""
        return None

    def write_brand_code(self, client, brand_id: int):
        """Write global brand code if supported."""
        if not self.supports_brand_write:
            return False
        return False
