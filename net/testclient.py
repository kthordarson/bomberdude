from concurrent.futures import ThreadPoolExecutor

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient
from random import randint
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
        self.clientid = ''.join([''.join(str(k)) for k in gen_randid()])
        self.readerr = 0
        print(f'[client] init {self.clientid}')
    @gen.coroutine
    def read(self):
        while True:
            try:
                data = yield self._stream.read_until(self.msg_separator)
                try:
                    body = data.rstrip(self.msg_separator)
                except TypeError as typerr:
                    print(f'[cr] {typerr}')
                    #body = str(self.clientid)
                print(f'[crl] b: {body}')
            except StreamClosedError as streamclosed:
                print(f'[cr] closed? {streamclosed} e: {self.readerr}')
                time.sleep(1)
                self.readerr += 1
            if self.readerr > 5:
                self.disconnect()
                return

    # @gen.coroutine
    # def send_update(self, data=None):
    #     encoded_data = data.encode('utf8')
    #     encoded_data +=  self.msg_separator 
    #     print(f'[cup] d: {encoded_data}')
    #     yield self._stream.write(encoded_data)

    @gen.coroutine
    def writexx(self):
        while True:
            try:
                #data = self.clientid  # yield self._executor.submit(input)
                if 'q' in data:
                    print(f'[cwl] q {data}')
                    self.disconnect()
                    return
                if data == 'foobar':
                    pass
                encoded_data = data.encode('utf8')
                encoded_data +=  self.msg_separator 
                if not encoded_data:
                    print(f'[cwl] not encoded_data s0: {encoded_data}')                    
                    break
                else:
                    #encoded_data = str(self.clientid) + data.encode('utf8') + self.msg_separator 
                    print(f'[cwl] s1: {encoded_data}')
                    yield self._stream.write(encoded_data)
            except StreamClosedError as streamerr:
                print(f'[cw] {streamerr}')
                time.sleep(1)
                # self.disconnect()
                # return

    @gen.coroutine
    def write(self, data=''):
        if data != '':
            try:
                #data = self.clientid  # yield self._executor.submit(input)
                if 'q' in data:
                    print(f'[cwl] q {data}')
                    self.disconnect()
                    return
                if data == 'foobar':
                    pass
                encoded_data = data.encode('utf8')
                encoded_data +=  self.msg_separator 
                if not encoded_data:
                    pass
                    #print(f'[cwl] not encoded_data s0: {encoded_data}')                    
                    #break
                else:
                    #encoded_data = str(self.clientid) + data.encode('utf8') + self.msg_separator 
                    print(f'[cwl] s1: {encoded_data}')
                    yield self._stream.write(encoded_data)
            except StreamClosedError as streamerr:
                print(f'[cw] {streamerr}')
                time.sleep(1)
            except AttributeError as attr_err:
                print(f'[cw] {attr_err}')
                time.sleep(1)
        else: 
            yield self._stream.write('fooo')
            # no data to send....

                # self.disconnect()
                # return

    @gen.coroutine
    def run(self, host, port):
        self._stream = yield self.connect(host, port)
        yield [self.read(), self.write()]

    def disconnect(self):
        super(Client, self).close()
        self._executor.shutdown(False)
        if not self._stream.closed():
            print('Disconnecting...')
            self._stream.close()

def gen_randid(seed=None):
    randid = []
    for k in range(0,7):
        n = randint(1,99)
        randid.append(n)
    return randid

@gen.coroutine
def connector(client=None):
#    print('Connecting to the server socket...')
#    client=Client()
    client = Client()
    client._stream = yield client.connect(host='127.0.0.1', port=5567)
    print(f'{client._stream}')
    yield [client.read(), client.write()]
    while True:
        client.write(data='asdfasdf')
    # IOLoop.instance().run_sync(lambda: client.connect(host='127.0.0.1', port=5567))
    # yield [client.read(), client.write()]
    # # client._stream = client.connect(host='127.0.0.1', port=5567)
    # while True:
    #     client.write(data='asdfasdf')
#    try:
#        yield Client().run('127.0.0.1', 5567)
#    except StreamClosedError as streamerr:
#        print(f'[c] Disconnected {streamerr}')

@gen.coroutine
def writer(client=None, data=None):
    # IOLoop.instance().run_sync(lambda: client.connect(host='127.0.0.1', port=5567))
    yield [client.read(), client.write()]
    # client._stream = client.connect(host='127.0.0.1', port=5567)


@gen.coroutine
def main1():
    print('Connecting to the server socket...')
    try:
        yield Client().run('127.0.0.1', 5567)
    except StreamClosedError as streamerr:
        print(f'[c] Disconnected {streamerr}')


if __name__ == '__main__':
    print(f'[clientstart]')
    
    # print(f'[client] client: {client}' )
    IOLoop.instance().run_sync(connector)
    #print(f'[client] _stream: {client._stream}' )
    # writer(client)
    # main()
    # IOLoop.instance().run_sync(main)
