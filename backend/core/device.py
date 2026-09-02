from enum import Enum


class DeviceType(Enum):

    # Standard Workstations
    PC = "pc"
    LAPTOP = "laptop"
    
    # Servers & Storage
    SERVER = "server"
    NAS = "nas"
    
    # Mobile & Smart Devices
    SMARTPHONE = "smartphone"
    TABLET = "tablet"
    SMART_TV = "smart_tv"
    
    # Network Peripherals
    PRINTER = "printer"
    IP_CAMERA = "ip_camera"
    IOT_DEVICE = "iot_device"
    
    # Fallback
    OTHER = "other"

