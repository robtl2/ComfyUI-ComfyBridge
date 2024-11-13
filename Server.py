from .Nodes import *
import socket
import threading
import io
from PIL import Image
import numpy as np
import torch
from server import PromptServer
from aiohttp import web
from .Event import EventMan
import json
import os



HOST = '0.0.0.0'
PORT = 17777

'''
-------------------------------------------------------------
--OpCodes--
'''
HANDSHAKE = 101
HEARTBEAT = 102

SEND_IMAGE = 201
REQUEST_IMAGE = 202
QUEUE_PROMPT = 203
RESPONSED_IMAGE = 204

PROGRESS = 301

ERROR = 404
OK = 666
'''
-------------------------------------------------------------
'''

ClientReceiverNames = {}
server_thread = None
client_threads = {}
connected = False

# 不知道comfyUI有没有给现成的setting获取方法，先这样写吧
def get_bridge_port_in_setting():
    global PORT

    settings_path = os.path.join(
        os.path.dirname(__file__), 
        '..', '..', 'user', 'default', 'comfy.settings.json'
    )
    
    with open(settings_path, 'r') as file:
        settings = json.load(file)

    try:    
        port = int(settings['cÖmfyBridge.port'])
    except:
        port = 17777

    PORT = port

def receiveInt(client_socket):
    return int.from_bytes(client_socket.recv(4), byteorder='big')

def receiveString(client_socket):
    length = receiveInt(client_socket)
    return client_socket.recv(length).decode('utf-8')

def sendString(client_socket, string):
    string_bytes = string.encode('utf-8')
    length_bytes = len(string_bytes).to_bytes(4, byteorder='big')
    data = length_bytes + string_bytes
    client_socket.sendall(data)

def sendInt(client_socket, code):
    client_socket.sendall(code.to_bytes(4, byteorder='big'))

def handleClient(client_socket):
    # 监听前端页面执行队列时的进度, 通过EventMan通知到ClientSocket
    EventMan.add('ProgressWithImageSender', onProgressWithImageSender, client_socket)
    # 等待前端页面执行完队列后，由ImageSender节点发送图片
    EventMan.add('ImageSenderGotImage', onImageSenderGotImage, client_socket)

    operations = SetupOperations(client_socket)

    while True:
        try:
            code = receiveInt(client_socket)
            if code in operations:
                operations[code]()
            else:
                closeClient(client_socket)
                print(f"ComfyBridge break for unknown opCode: {code}")
        except Exception as e:
            print(f"ComfyBridge {e}")
            EventMan.remove('ProgressWithImageSender', onProgressWithImageSender, client_socket)
            EventMan.remove('ImageSenderGotImage', onImageSenderGotImage, client_socket)

            ClientReceiverNames.pop(client_socket, None)
            closeClient(client_socket)
            break

def closeClient(client_socket):
    client_socket.close()
    client_thread = client_threads.pop(client_socket, None)
    try:    
        if client_thread:
            client_thread.join()
    except Exception as e:
        pass

def startSocketServer():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((HOST, PORT))
            server_socket.listen(16)
            print("ComfyBridge listened at port:", PORT)

            while connected:
                client_socket, addr = server_socket.accept()
                print("ComfyBridge accept client: ", addr)
                client_thread = threading.Thread(target=handleClient, args=(client_socket,))
                client_threads[client_socket] = client_thread
                client_thread.start()
    except Exception as e:
        print(f"ComfyBridge error: {e}")

# 接收客户端发送给ImageReceiver节点的图片
def whenClientSendImage(client_socket):
    try:
        name_length = receiveInt(client_socket)

        for _ in range(name_length):
            name = receiveString(client_socket)
            image_length = receiveInt(client_socket)
            image_data = b''
            while len(image_data) < image_length:
                packet = client_socket.recv(min(4096, image_length - len(image_data)))
                image_data += packet

            image = Image.open(io.BytesIO(image_data))
            image_tensor = torch.from_numpy(np.array(image)).float() / 255.0
            image_tensor = image_tensor.unsqueeze(0)

            # 给ImageReceiver节点调用
            if name not in IMAGE_RECEIVED:
                IMAGE_RECEIVED[name] = {"data":image_tensor, "counter":0}
            else:
                IMAGE_RECEIVED[name]["data"] = image_tensor
                IMAGE_RECEIVED[name]["counter"] += 1
            
        sendInt(client_socket, OK)
    except Exception as e:
        print(f"ComfyBridge receiving image with error: {e}")
        sendInt(client_socket, ERROR)
        
# 接收客户端请求的ImageSender节点的name: List<String>
def whenClientRequestImage(client_socket):
    try:
        name_length = receiveInt(client_socket)
        names = []
        for _ in range(name_length):
            names.append(receiveString(client_socket))
        
        ClientReceiverNames[client_socket] = names

        sendInt(client_socket, OK)
    except Exception as e:
        print(f"ComfyBridge sending image with error: {e}")
        sendInt(client_socket, ERROR)

def whenClientQueuePrompt(client_socket):
    names = ClientReceiverNames[client_socket]
    PromptServer.instance.send_sync("ComfyBridge.QueuePrompt", {"names": names})

def onProgressWithImageSender(client_socket, args):
    socket = client_socket
    progress = args['progress']
    max = args['max']

    receiver_names = ClientReceiverNames[client_socket]
    current_names = args['senders']

    will_response = set(receiver_names) & set(current_names)

    if will_response:
        sendInt(socket, PROGRESS)
        socket.sendall(progress.to_bytes(4, byteorder='big'))
        socket.sendall(max.to_bytes(4, byteorder='big'))

def onImageSenderGotImage(client_socket, args):
    image_data = args['image']
    receiver_names = ClientReceiverNames[client_socket]

    if args['name'] in receiver_names:
        sendInt(client_socket, RESPONSED_IMAGE)
        sendString(client_socket, args['name'])
        length_bytes = len(image_data).to_bytes(4, byteorder='big') 
        data = length_bytes + image_data
        client_socket.sendall(data)
        sendInt(client_socket, OK)
    else:
        sendInt(client_socket, ERROR)

def SetupOperations(client_socket):
    operations = {
        HANDSHAKE: lambda: sendInt(client_socket, HANDSHAKE),
        SEND_IMAGE: lambda: whenClientSendImage(client_socket),
        REQUEST_IMAGE: lambda: whenClientRequestImage(client_socket),
        QUEUE_PROMPT: lambda: whenClientQueuePrompt(client_socket),
        HEARTBEAT: lambda: sendInt(client_socket, HEARTBEAT)
    }
    return operations


def StartComfyBridge():
    global connected
    global server_thread
    print("start ComfyBridge")
    get_bridge_port_in_setting()

    connected = True
    server_thread = threading.Thread(target=startSocketServer)
    server_thread.daemon = True 
    server_thread.start()

def StopComfyBridge():
    print("stop ComfyBridge")
    global connected
    global server_thread

    connected = False
    if server_thread:
        server_thread.join()
        server_thread = None

    for client_socket in client_threads:
        closeClient(client_socket)
    print("ComfyBridge stopped")

########################################################
"""
从js页面传过来的消息, 通过EventMan通知到ClientSocket
"""
routes = PromptServer.instance.routes

@routes.post('/comfyBridge_progress')
async def progress(request):
    value = await request.post()
    senders = json.loads(value.get('senders'))
    progress = int(value.get('progress'))
    max = int(value.get('max'))

    EventMan.trigger('ProgressWithImageSender', {'senders': senders, 'progress': progress, 'max': max})
    return web.json_response({})





