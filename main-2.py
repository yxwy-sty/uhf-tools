import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.web import StaticFileHandler 
from tornado.options import define, options

import os
import asyncio
import threading
import queue
import time

define('debug', type=bool, default=False, help='run in debug mode with autoreload (default: false)')
define('device', type=str, default="/dev/ttyUSB0", help='serial device path (default: /dev/ttyUSB0)')
define('port', type=int, default="8000", help='listent port (default: 8000)')


activeClients = set()
class WsConnectHandler(tornado.websocket.WebSocketHandler) :
    
    def initialize(self, readerQueue, writerQueue):
        self.readerQueue = readerQueue
        self.writerQueue = writerQueue
        
    def check_origin(self, origin) :
        '''重写同源检查 解决跨域问题'''
        return True

    def open(self) :
        activeClients.add(self)
        self.write_message('Welcome')

    @classmethod
    def broadcast(self, readerQueue) :
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            output = readerQueue.get()
            print("read one ...", len(activeClients), output)
            for client in activeClients:
                try:
                    client.write_message(output) 
                except:
                    pass
        
    def on_close(self) :
        '''websocket连接关闭后被调用'''
        self.write_message('Bye')
        activeClients.remove(self)

    def on_message(self, message) :
        '''接收到客户端消息时被调用'''
        self.write_message('new message :' + message)  # 向客服端发送


class MainHandler(tornado.web.RequestHandler) :
    def initialize(self, readerQueue, writerQueue):
        self.readerQueue = readerQueue
        self.writerQueue = writerQueue
        
    def get(self):
        self.readerQueue.put("command output")
        self.write("Hello world from readerQueue")
        
    def post(self):
        self.writerQueue.put("writer command")
        self.write("Hello world from writerQueue")

class TTYService():
    def __init__(self, readerQueue, writerQueue, ttyPath):
        threading.Thread.__init__(self)
        self.readerQueue = readerQueue
        self.writerQueue = writerQueue
        self.ttyPath = ttyPath
    
    def connect(self):
        print("打开设备中...")
        
    def readerHander(self):
        print("准备读取设备返回结果，返回所有客户端")
        index = 0
        while True:
            index += 1
            output = self.readerQueue.put("test-%d" % (index,))
            time.sleep(5)
            #await asyncio.sleep(5)
            
    def writeHander(self):
        print("收到指令，发给模块")
        while True:
            command = self.writerQueue.get()
            print("write one ...", command)
        
    def ttyClose(self):
        pass
        
    # def run(self):
        # self.ttyOpen()
        # ioloop = asyncio.new_event_loop()
        # asyncio.set_event_loop(ioloop)
        # tasks = [
            # ioloop.create_task(self.writeHander()),
            # ioloop.create_task(self.readerHander()),
        # ]
        
        # ioloop.run_until_complete(asyncio.wait(tasks))
        # ioloop.close()
        
    
        
class Application(tornado.web.Application) :

    def __init__(self, readerQueue, writerQueue):
 
        handlers = [
            (r'/$', MainHandler, dict(readerQueue=readerQueue, writerQueue=writerQueue)),
            (r'/manager/(.*)', StaticFileHandler, {"path":os.path.join(os.path.dirname(__file__), "uhf-tools", "manager"), "default_filename":"index.html"}),
            (r'/ws', WsConnectHandler, dict(readerQueue=readerQueue, writerQueue=writerQueue)),
        ]
        settings = {
            'static_path':  os.path.join(os.path.dirname(__file__), "uhf-tools"),
            'autoreload': True,
            'debug': options.debug,
            'static_url_prefix': '/static/' 
        }
        
        tornado.web.Application.__init__(self, handlers, **settings)


if __name__ == "__main__" :
    tornado.options.parse_command_line()
    # 读取设备响应序列
    readerQueue = queue.Queue()
    # 发送设备指令序列
    writerQueue = queue.Queue()
    ttyService = TTYService(readerQueue, writerQueue, options.device)
    ttyService.connect()
    t1 = threading.Thread(target = ttyService.readerHander)
    t2 = threading.Thread(target = ttyService.writeHander)
    t3 = threading.Thread(target = WsConnectHandler.broadcast, args=(readerQueue,))
    t1.start()
    t2.start()
    t3.start()
    app = Application(readerQueue, writerQueue)
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()
