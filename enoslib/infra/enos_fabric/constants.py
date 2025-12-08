#: Walltime
DEFAULT_WALLTIME = "24:00"


#: Site
DEFAULT_SITE = "UCSD"


#: Image
DEFAULT_IMAGE = "default_rocky_8"


# User
DEFAULT_USER = "root"


#: Sizes of the machines available for the configuration
FLAVOURS: dict[str, dict] = {
    "tiny": {"core": 1, "mem": 0.5},
    "small": {"core": 1, "mem": 1},
    "medium": {"core": 2, "mem": 2},
    "big": {"core": 2, "mem": 3},
    "large": {"core": 4, "mem": 4},
    "extra-large": {"core": 6, "mem": 6},
}


#: Default flavour
DEFAULT_FLAVOUR: tuple[str, dict[str, dict]] = ("tiny", FLAVOURS["tiny"])


#: Default number of machines
DEFAULT_NUMBER = 1


#: Default name prefix
DEFAULT_NAME_PREFIX = "fabric"


#:
FABNETV4 = "FABNetv4"


#:
FABNETV6 = "FABNetv6"


#:
FABNETV4EXT = "FABNetv4Ext"


#:
FABNETV6EXT = "FABNetv6Ext"


#:
L3VPN = "L3VPN"


#:
L2BRIDGE = "L2Bridge"


#:
L2STS = "L2STS"


#:
L2PTP = "L2PTP"


#:
PORTMIRROR = "PortMirror"


#:
NVME = "NVME"


#:
STORAGE = "Storage"


#:
STORAGE_MODEL_NAS = "NAS"


#:
STORAGE_MODEL_P4510 = "P4510"


#:
NIC = "NIC"


#:
NIC_SHARED = "SharedNIC"


#:
NIC_BASIC = "NIC_Basic"


#:
NIC_SMART = "SmartNIC"


#:
NIC_MODEL_CONNECTX_5 = "ConnectX-5"


#:
NIC_MODEL_CONNECTX_6 = "ConnectX-6"


#:
GPU = "GPU"


#:
GPU_MODEL_TESLA_T4 = "TeslaT4"


#:
GPU_MODEL_RTX_6000 = "RTX6000"


#:
GPU_MODEL_A30 = "A30"


#:
GPU_MODEL_A40 = "A40"


#:
PERMISSION_SLICE_MULTISITE = "Slice.Multisite"


#:
PERMISSION_NVME = "Component.NVME"


#:
PERMISSION_NVME_P4510 = "Component.NVME_P4510"


#:
PERMISSION_STORAGE = "Component.Storage"


#:
PERMISSION_GPU = "Component.GPU"


#:
PERMISSION_FABNETV4_EXT = "Net.FABNetv4Ext"


#:
PERMISSION_FABNETV6_EXT = "Net.FABNetv6Ext"


#:
PERMISSION_PORTMIRROR = "Net.PortMirroring"


#:
PERMISSION_CONNECTX_5 = "Component.SmartNIC_ConnectX_5"


#:
PERMISSION_CONNECTX_6 = "Component.SmartNIC_ConnectX_6"


#:
PERMISSION_CONNECTX_7_100 = "Component.SmartNIC_ConnectX_7_100"


#:
PERMISSION_CONNECTX_7_400 = "Component.SmartNIC_ConnectX_7_400"
