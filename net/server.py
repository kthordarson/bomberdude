import signal
import asyncio
import os
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.platform.asyncio import AsyncIOMainLoop, to_asyncio_future
import aioredis


class ClientConnection(object):
    """
    This class represents single socket connection. Socket listening works in
    parallel with Redis channel updates listening.
    """
    message_separator = b'|'

    def __init__(self, stream):
        print(f'[srv] connect from {stream.socket.getpeername()}')
        self._stream = stream
        self._subscribed = False

    def _handle_request(self, request):
        if request == 'SUBSCRIBE':
            if not self._subscribed:
                self._subscribed = True
                return 'CONFIRMED'
            else:
                return 'ALREADY SUBSCRIBED'
        elif request == 'UNSUBSCRIBE':
            if not self._subscribed:
                return 'ALREADY UNSUBSCRIBED'
            else:
                self._subscribed = False
                return 'CONFIRMED'
        elif request == 'foobar':
            return '[_barfoo_]'
        else:
            #print(f'[srv] d: {request}')
            return f'{request}'
            # return 'UNKNOWN COMMAND'

    @gen.coroutine
    def run(self):
        """
        Main connection loop. Launches listen on given channel and keeps
        reading data from socket until it is closed.
        """
        # print(f'[clientconnection ] run')
        try:
            while True:
                try:
                    request = yield self._stream.read_until(self.message_separator)
                    request_body = request.rstrip(self.message_separator)
                    request_body_str = request_body.decode('utf-8')
                except StreamClosedError:
                    self._stream.close(exc_info=True)
                    return
                except AttributeError as e_attrib:
                    print(f'[conn] AttributeError {e_attrib}')
                else:
                    response_body = self._handle_request(request_body_str)
                    response_body_bytes = response_body.encode('utf-8')
                    response = response_body_bytes + self.message_separator
                    print(f'[server] got: {response}')
                    try:
                        yield self._stream.write(response)
                    except StreamClosedError as e_stream:
                        print(f'[conn] Err {e_stream}')
                        self._stream.close(exc_info=True)
                        return
                    except AttributeError as e_attrib:
                        print(f'[conn] AttributeError {e_attrib}')

        except Exception as e_exception:
            if not isinstance(e_exception, gen.Return):
                print(f"Connection loop has experienced an error. {e_exception}")
            else:
                print(f'Closing connection loop because socket was closed. {e_exception}')

    @gen.coroutine
    def update(self, message):
        """
        Handle updates and send data if necessary.

        :param message: variable that represents the update message
        """
        if not self._subscribed:
            return
        response = message + self.message_separator
        try:
            yield self._stream.write(response)
        except StreamClosedError:
            self._stream.close(exc_info=True)
            return


class Server(TCPServer):
    """
    This is a TCP Server that listens to clients and handles their requests
    made using socket and also listens to specified Redis ``channel`` and
    handles updates on that channel.
    """
    def __init__(self,  *args, **kwargs):
        print(f'[Server] __init__')
        super(Server, self).__init__(*args, **kwargs)
        self._redis = None
        self._channel = None
        self._connections = []
        self.clients = []
        self.start1 = False
        self.start2 = False

    # @asyncio.coroutine
    def subscribe(self, channel_name):
        """
        Create async redis client and subscribe to the given PUB/SUB channel.
        Listen to the messages and launch publish handler.

        :param channel_name: string representing Redis PUB/SUB channel name
        """
        print(f'[server] subscribe')
        self._redis = yield aioredis.create_redis(('127.0.0.1', 6379))
        channels = yield self._redis.subscribe(channel_name)
        print('[server] Subscribed to "{}" Redis channel.'.format(channel_name))
        self._channel = channels[0]
        yield self.listen_redis()

    @gen.coroutine
    def listen_redis(self):
        """
        Listen to the messages from the subscribed Redis channel and launch
        publish handler.
        """
        print(f'[server] listen_redis')
        while True:
            yield self._channel.wait_message()
            try:
                msg = yield self._channel.get(encoding='utf-8')
            except aioredis.errors.ChannelClosedError:
                print("Redis channel was closed. Stopped listening.")
                return
            if msg:
                body_utf8 = msg.encode('utf-8')
                yield [con.update(body_utf8) for con in self._connections]
            print("Message in {}: {}".format(self._channel.name, msg))

    @gen.coroutine
    def handle_stream(self, stream, address):
        print(f'[srv] incoming request from {address}')
        connection = ClientConnection(stream)
        self._connections.append(connection)
        self.clients.append(connection)
        yield connection.run()
        self._connections.remove(connection)
        self.clients.remove(connection)

    @gen.coroutine
    def shutdown(self):
        super(Server, self).stop()
        try:
            yield self._redis.unsubscribe(self._channel)
            yield self._redis.quit()
            self.io_loop.stop()
        except AttributeError as e_attrib:
            #self.io_loop.stop()
            print(f'[shutdown] {e_attrib}')
            os._exit(0)  # pylint: disable=protected-access
        #finally:
            # yield self._redis.quit()
            #self.io_loop.stop()

    @gen.coroutine
    def start_server(self):
        pass
    
def sig_handler(sig, frame):  # pylint: disable-missing-function-docstring
    print('Caught signal: {}'.format(sig))
    os._exit(1)
    IOLoop.current().add_callback_from_signal(server.shutdown)

def create_server():

    # server = Server()
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    AsyncIOMainLoop().install()
    server.listen(port=5567, address='127.0.0.1')
    IOLoop.current().spawn_callback(server.subscribe, 'updates')

    print('Starting the server...')
    asyncio.get_event_loop().run_forever()
    return server
    # print('Server has shut down.')


if __name__ == '__main__':
    print('creating server')
    server = Server()
    print(f'starting server {server}')
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    AsyncIOMainLoop().install()
    server.listen(port=5567, address='127.0.0.1')
    print(f'[srv] {server}')
    IOLoop.current().spawn_callback(server.subscribe, 'updates')
    server.start1 = True
    print(f'Starting the server1: {server.start1}')
    asyncio.get_event_loop().run_forever()
    server.start2 = True
    print(f'Starting the server2: {server.start2}')
#    server.start_server()
    print(f'[s] {server.start1} {server.start2} ')
