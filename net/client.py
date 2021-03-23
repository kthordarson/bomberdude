from concurrent.futures import ThreadPoolExecutor
from random import randint
from socket import SO_EXCLUSIVEADDRUSE
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient
from datetime import datetime
import time

class Client(TCPClient):
    """
    TCP Client that simultaneously reads from and writes to the socket.
    """
    msg_separator = b'|'

    def __init__(self):
        super(Client, self).__init__()
        self._stream = None
        self._executor = ThreadPoolExecutor(1)
        self.client_id = ''.join([''.join(str(k)) for k in gen_randid()])
        self.databuffer = []
        print(f'[client] __init__ {self.client_id}')

    @gen.coroutine
    def run(self, host, port):
        self._stream = yield self.connect(host, port)
        yield [self.read(), self.write()]

    @gen.coroutine
    def read(self):
        while True:
            try:
                data = yield self._stream.read_until(self.msg_separator)
                body = data.rstrip(self.msg_separator)
                print(f'[clientread {self.client_id}] body: {body}')
            except StreamClosedError:
                self.disconnect()
                return

    @gen.coroutine
    def write(self):
        while True:
            try:
                data = ''
                data = self.client_id + '|' + self.databuffer #  yield self._executor.submit(input)
                encoded_data = data.encode('utf8')
                encoded_data += self.msg_separator
                print(f'[client] ed: {encoded_data}')
                time.sleep(1)
                yield self._stream.write(encoded_data)
            except StreamClosedError:
                self.disconnect()
                return

    def printstatus(self):
        print(f'[client] id:{self.client_id}')

    def disconnect(self):
        super(Client, self).close()
        self._executor.shutdown(False)
        if not self._stream.closed():
            print(f'[client {self.client_id}] Disconnecting...')
            self._stream.close()

def gen_randid(seed=None):
    randid = []
    for k in range(0,7):
        n = randint(1,99)
        randid.append(n)
    return randid

@gen.coroutine
def main():
    print('Connecting to the server socket...')
    yield Client().run('127.0.0.1', 5567)
    print('Disconnected from server socket.')


if __name__ == '__main__':
    IOLoop.instance().run_sync(main)
