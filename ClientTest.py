import asyncio
from Event import EventMan

SERVER = {
    'HOST': 'localhost',
    'PORT': 17777
}

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

op_queue = []
op_queue_args = []
reader = None
writer = None

reader_lock = asyncio.Lock()
writer_lock = asyncio.Lock()

async def connectToComfyBridge():
    global reader, writer
    reader, writer = await asyncio.open_connection(SERVER['HOST'], SERVER['PORT'])

async def sendInt(opCode):
    async with writer_lock:
        writer.write(opCode.to_bytes(4, byteorder='big'))
        await writer.drain()   

async def sendString(string):
    string_bytes = string.encode('utf-8')
    length_bytes = len(string_bytes).to_bytes(4, byteorder='big')
    async with writer_lock:
        writer.write(length_bytes)
        writer.write(string_bytes)
        await writer.drain()

async def sendImage(image_data):
    image_length_bytes = len(image_data).to_bytes(4, byteorder='big')
    async with writer_lock:
        writer.write(image_length_bytes)
        writer.write(image_data)
        await writer.drain()

async def receiveInt():
    async with reader_lock:
        int_bytes = await reader.readexactly(4)

    return int.from_bytes(int_bytes, byteorder='big')

async def receiveString():
    async with reader_lock:
        length_bytes = await reader.readexactly(4)
        length = int.from_bytes(length_bytes, byteorder='big')
        string_bytes = await reader.readexactly(length)
        return string_bytes.decode('utf-8') 

async def receiveImage():
    async with reader_lock: 
        length_bytes = await reader.readexactly(4)
        length = int.from_bytes(length_bytes, byteorder='big')
        image_bytes = await reader.readexactly(length)
        
    return image_bytes

async def heartbeat():
    async def delayDo():
        await asyncio.sleep(10)
        await sendInt(HEARTBEAT)
    asyncio.create_task(delayDo())

async def closeSocket():
    global reader, writer
    reader.close()
    writer.close()
    await writer.wait_closed()
    reader = None
    writer = None


'''
-------------------------------------------------------------
--Operations--
'''
async def op_sendImages(names, image_datas):
    if len(names) != len(image_datas):
        return False
    
    await sendInt(SEND_IMAGE)
    await sendInt(len(names))

    for i in range(len(names)):
        await sendString(names[i])
        await sendImage(image_datas[i])

async def op_sendRequestNames(names):
    await sendInt(REQUEST_IMAGE)
    await sendInt(len(names))
    for name in names:
        await sendString(name)

async def op_queuePrompt():
    await sendInt(QUEUE_PROMPT)
'''
-------------------------------------------------------------
'''

async def operation_loop():
    await sendInt(HANDSHAKE)
    opCode = await receiveInt()

    if opCode == HANDSHAKE:
        print('Handshake success')
        await sendInt(HEARTBEAT)
        while True:
            try:
                if len(op_queue) > 0:
                    op = op_queue.pop(0)
                    args = op_queue_args.pop(0)
                    await op(*args)
            except Exception as e:
                print(f"Error in asyncSocketLoop: {e}")
                break
            await asyncio.sleep(0.1)
    else:
        print('Handshake failed')
        return

def AddOperation(op, *args):
    op_queue.append(op)
    op_queue_args.append(args)

async def client_loop():
    while True:
        code = await receiveInt()

        if code == HEARTBEAT:
            await heartbeat()
        elif code == RESPONSED_IMAGE:
            name = await receiveString()
            image_data = await receiveImage()
            print(f'Received image: {name}')
            EventMan.trigger('on_image_received', {'name':name, 'data':image_data})
        elif code == PROGRESS:
            progress = await receiveInt()
            max = await receiveInt()
            print(f'Progress: {progress}/{max}')
            EventMan.trigger('on_progress', {'progress':progress, 'max':max})

        await asyncio.sleep(0.1)

async def Run():
    await connectToComfyBridge()
    task = asyncio.create_task(operation_loop())
    asyncio.create_task(client_loop())
    try:
        await task
    except Exception as e:
        print(f"Error in socket task: {e}")
        await closeSocket()
    
def test():
    image_names = ['img2img']
    file_paths = ['/Users/luoyong/Downloads/www/writer/face.png']

    request_names = ['test']
    receive_image_dir = '/Users/luoyong/Desktop'
    
    image_datas = []
    for file_path in file_paths:
        with open(file_path, 'rb') as f:
            image_datas.append(f.read())

    def on_image_received(pack):
        request_name = pack['name']
        image_data = pack['data']
        with open(f'{receive_image_dir}/{request_name}.png', 'wb') as f:
            f.write(image_data)
        

    EventMan.add('on_image_received', on_image_received)

    AddOperation(op_sendImages, image_names, image_datas)
    AddOperation(op_sendRequestNames, request_names)
    AddOperation(op_queuePrompt)

test()
asyncio.run(Run())


