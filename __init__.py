from .Nodes import *
from .Server import StartComfyBridge

WEB_DIRECTORY = "./web/js"

StartComfyBridge()

NODE_CLASS_MAPPINGS = {
    "CB_ImageReceiver": ImageReceiver,
    "CB_ImageSender": ImageSender,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CB_ImageReceiver": "ImageReceive੭˚⁺",
    "CB_ImageSender": "ImageSende੭⁺˚",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', "WEB_DIRECTORY"]