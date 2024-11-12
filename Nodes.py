import numpy as np
import torch
from PIL import Image
import io
from .Event import EventMan

IMAGE_RECEIVED = {}

emptyImage = torch.from_numpy(np.ones((64, 64, 3), dtype=np.uint8)).float().unsqueeze(0)

class ImageReceiver:
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "execute"
    CATEGORY = "SimpleStuff"
    OUTPUT_NODE = True

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {
                    "default": "img2img", 
                })
            },
        }
    
    @classmethod
    def IS_CHANGED(cls, name):
        counter = -1
        if name in IMAGE_RECEIVED:
            counter = IMAGE_RECEIVED.get(name)['counter']
        return float(counter)
    
    def execute(self, name):
        if name in IMAGE_RECEIVED:
            image = IMAGE_RECEIVED.get(name)['data']
            return (image,)
        else:
            return (emptyImage,)
    
class ImageSender:
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "execute"
    CATEGORY = "SimpleStuff"
    OUTPUT_NODE = True

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "name": ("STRING", {
                    "default": "name", 
                }),
                "image": ("IMAGE",)
            },
        }
    
    @classmethod
    def IS_CHANGED(cls, name, image):
        return float("NaN")
    
    def execute(self, name, image):
        img = Image.fromarray((image.squeeze(0).numpy() * 255).astype(np.uint8))
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        EventMan.trigger('ImageSenderGotImage', {'name': name, 'image':buffered.getvalue()})

        return ()
