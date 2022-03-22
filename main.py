import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.web import StaticFileHandler 
from tornado.options import define, options

import os
import tornado.gen as gen
import tornado.queues as queue
import logging

define('debug', type=bool, default=False, help='run in debug mode with autoreload (default: false)')
define('device', type=str, default="/dev/ttyUSB0", help='serial device path (default: /dev/ttyUSB0)')
define('port', type=int, default="8000", help='listent port (default: 8000)')


active_clients = set()
class WsConnectHandler(tornado.websocket.WebSocketHandler) :
    
    def check_origin(self, origin) :
        '''重写同源检查 解决跨域问题'''
        return True

    def open(self) :
        active_clients.add(self)
        self.write_message('Welcome')

    @classmethod
    @gen.coroutine
    def broadcast(self, readerQueue) :
        while True:
            output = yield readerQueue.get()
            print("read one ...", len(active_clients), output)
            for client in active_clients:
                try:
                    client.write_message(output) 
                except:
                    pass
        
    def on_close(self) :
        '''websocket连接关闭后被调用'''
        active_clients.remove(self)

    def on_message(self, message) :

        self.application.writerQueue.put(message)
        '''接收到客户端消息时被调用'''
        self.write_message('Received %s' % (message, ))  # 向客服端发送


class MainHandler(tornado.web.RequestHandler) :

    def get(self):
        self.application.readerQueue.put("command output")
        self.write("done")
        
    def post(self):
        self.application.writerQueue.put("writer command")
        self.write("done")

class TTYService():
    def __init__(self, readerQueue, writerQueue, ttyPath):
        self.readerQueue = readerQueue
        self.writerQueue = writerQueue
        self.ttyPath = ttyPath
    
    def connect(self):
        print("打开设备中...")
        
    @gen.coroutine    
    def readerHander(self):
        print("准备读取设备返回结果，返回所有客户端")
        index = 0
        while True:
            index += 1
            self.readerQueue.put_nowait("test-%d" % (index,))
            yield gen.sleep(5)
            
    @gen.coroutine
    def writeHander(self):
        print("收到指令，发给模块")
        while True:
            command = yield self.writerQueue.get()
            logging.info("write command: " + command)
        
    def ttyClose(self):
        pass
        
    def run(self):
        self.ttyOpen()

        
class Application(tornado.web.Application) :

    def __init__(self, readerQueue, writerQueue):
        self.readerQueue = readerQueue
        self.writerQueue = writerQueue
        handlers = [
            (r'/$', MainHandler),
            (r'/manager/(.*)', StaticFileHandler, {"path":os.path.join(os.path.dirname(__file__), "uhf-tools", "manager"), "default_filename":"index.html"}),
            (r'/ws', WsConnectHandler)
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
    # 开启读/写/广播任务
    ttyService = TTYService(readerQueue, writerQueue, options.device)
    app = Application(readerQueue, writerQueue)
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().add_callback(ttyService.writeHander)
    tornado.ioloop.IOLoop.current().add_callback(ttyService.readerHander)
    tornado.ioloop.IOLoop.current().add_callback(WsConnectHandler.broadcast, readerQueue)
    tornado.ioloop.IOLoop.current().start()
