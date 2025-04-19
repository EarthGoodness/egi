"""Adapter factory logic for EGI VRF integration."""

from .solo import AdapterSolo
from .vrf_light import AdapterVrfLight
from .vrf_pro import AdapterVrfPro

def get_adapter(adapter_type: str):
    """
    Return the appropriate adapter instance based on the adapter_type string.
    Valid types: 'solo', 'light', 'pro'.
    Defaults to VRF Light if type is unknown.
    """
    if adapter_type == "solo":
        return AdapterSolo()
    elif adapter_type == "pro":
        return AdapterVrfPro()
    else:
        return AdapterVrfLight()
