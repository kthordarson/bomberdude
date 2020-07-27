# netstuff
import socket
import os
import time
from threading import Thread, Event
import asynchat, asyncore
from rencode import loads, dumps
import pickle
import random
import io

class Server(Thread):
    def __init__(self, game_data):
        super(Server, self).__init__()
        self.game_data = game_data
        self.hostname = socket.gethostname()
        self.ipaddress = get_ip_address()
        self.localIP = self.ipaddress  # '127.0.0.1'
        self.localPort = 10102
        self.bufferSize = 1024
        self.listening = False
        # self.msgFromServer = "Hello UDP Client"
        # self.bytesToSend = str.encode(self.msgFromServer)
        self.foobar = str.encode('foobar')
        self.clients = []
        self.client_conn = []
        self.connections = 0
        self._stop_event = Event()
        self.servername = 'stjani'

    def send_map(self, client):
        data = pickle.dumps(self.game_data.game_map)
        data_to_send = io.BytesIO(data)
        data_size = data_to_send.getbuffer().nbytes
        # fsize = struct.unpack('!I', b''.join(chunks))[0]
        print(f'[server][send_map] sending [mapstart] datatype: {type(self.game_data)} client: {client} d: {len(data)} {type(data)} ds:{type(data_to_send)} sdl:{data_size}')
        command = str.encode('[mapstart]'+str(data_size))
        self.UDPServerSocket.sendto(command, client)
        while True:
            chunk = data_to_send.read(self.bufferSize)
            if not chunk:
                break
            self.UDPServerSocket.sendto(chunk, client)
            print(f'[server][send_map] sending ... ')
        print(f'[server][send_map][mapend]')
        self.UDPServerSocket.sendto(str.encode('[mapend]'), client)

    def client_connection(self, client):
        print(f'[server][client_connection] connections: {self.connections}')
        if self.connections <= 3:
            id = str(random.randint(30,99))
            self.bytesToSend = str.encode('yourid:' + id)
            self.UDPServerSocket.sendto(self.bytesToSend, client)
            self.connections += 1
            self.clients.append(client)
            print(f'[server][client_connection] sending playerid: {id} to {client} totalconnections: {self.connections}')
            return id
        else:
            id = '0'
            self.bytesToSend = str.encode('yourid:' + id)
            self.UDPServerSocket.sendto(self.bytesToSend, client)
            print(f'[server][client_connection] ERR id: {id} connections: {self.connections}')
            return id

    def add_client(self, player):
        self.clients.append(player)

    def create_socket(self):
        try:
            self.UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.UDPServerSocket.bind((self.localIP, self.localPort))
            self.listening = True
            print(f'[Server] create socket')
        except Exception as e:
            print(f'[server] create socket err {e}')
            self.listening = False
            # os._exit(1)

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def kill(self):
        self.listening = False

    def run(self):
        print(f'[Server] run ...')
        while self.listening:
            try:
                data = self.UDPServerSocket.recvfrom(self.bufferSize)
                if not data:
                    break
                else:
                    command = data[0].decode()
                    #print(f'[server][gotdata] {data}')
                    if command[:7] == '[getid]':
                        print(f'[server][gotdata] {data}')
                        self.client_connection(data[1])
                    if command[:7] == '[event]':
                        print(f'[server][gotdata] {data}')
                    if command[:11] == '[playerpos]':
                        print(f'[server][gotdata] {data}')
                    if command[:8] == '[foobar]':
                        print(f'[server][gotdata] {data}')
                        new_client = data[1]
                        self.client_conn.append(new_client)
                        self.send_server_info(new_client)
                    if command[:8] == '[getmap]':
                        self.send_map(data[1])
                    else:
                        pass
                        # print(f'[server][gotdata] UNKNOWN {data}')
            except Exception as e:
                print(f'[server][err] {e}')

    def send_server_info(self, client):
        print(f'[server][send_info] {client}')
        self.bytesToSend = str.encode(f'[serveripaddress]{self.ipaddress}')
        self.UDPServerSocket.sendto(self.bytesToSend, client)

    def send(self):
        if len(self.clients) >= 1:
            for client in self.clients:
                self.bytesToSend = str.encode('FOO test')
                print(f'[server] sending {self.bytesToSend} to {client} l:{len(self.clients)}')
                self.UDPServerSocket.sendto(self.bytesToSend, client)
        else:
            print(f'[server] No clients connected...')




class Client(Thread):
    def __init__(self):
        super(Client, self).__init__()
        # self.bytesToSend = str.encode(self.msgFromClient)
        #self.serverAddressPort = ("127.0.0.1", 10102)
        self.bufferSize = 1024
        self.connected = False
        self.hostname = socket.gethostname()
        # self.ipaddress = socket.gethostbyname(self.hostname)
        self.ipaddress = get_ip_address()
        self.client_id = 0
        self.foundservers =[]
        self.new_map = None
        self.got_new_map = True

    def create_socket(self):
        try:
            self.UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            # self.UDPClientSocket.bind(self.serverAddressPort)
            self.got_socket = True
            print(f'[client] socket created: {self.UDPClientSocket}')
        except Exception as e:
            print(f'[client][create_socket] exception {e}')
            self.connected = False
            self.got_socket = False

    def request_map(self, server):
        dataraw = None
        chunks = []
        command = str.encode('[getmap]')
        print(f'[client][request_map]')
        self.UDPClientSocket.sendto(command, server)
        print(f'[client][request_map] waiting for response...')
        time.sleep(0.5)
        try:
            dataraw = self.UDPClientSocket.recvfrom(self.bufferSize)
            data = dataraw[0].decode()
        except Exception as e:
            print(f'[client][request_map] {e}')
        if data:
            if data[:10] == '[mapstart]':
                print(f'[client][mapstart] size:{data[10:]}')
                data_size = int(data[10:])
                received = 0
                while received < data_size:
                    mapdata = self.UDPClientSocket.recv(min(data_size - received, self.bufferSize))
                    received += len(mapdata)
                    chunks.append(mapdata)                            
                    print(f'[client][dlmap] {received} {data_size} {len(mapdata)}')
                self.new_map = pickle.load(chunks)
                self.got_new_map = True
                print(f'[client][new_map] {type(self.new_map)}')
            else:
                print(f'[client] UNKNOWN {data} {data[:10]}')


    def set_id(self, id):
        print(f'[client][set_id] old {self.client_id} new {id}')
        self.client_id = id

    def run(self):
#        if not self.connected:
#            print(f'[client][run] not connected ... ')
#            self.connect_to_server()

        while True:
            dataraw = None
            try:
                dataraw = self.UDPClientSocket.recvfrom(self.bufferSize)                
            except Exception as e:
                print(f'[client][run] {e} gotsocket:{self.got_socket}')
            if not dataraw or dataraw is None:
                break
            else:
                chunks = []
                data = dataraw[0].decode()
#                if data[:7] == 'yourid:':
#                    self.client_id = int(data[7:10])
#                    self.set_id(self.client_id)
#                    self.connected = True
#                    print(f'[client][gotdata] {data} {self.client_id}')
                if data[:17] == '[serveripaddress]':
                    self.foundservers.append('')
                    print(f'[client][foundserver] {data}')
                if data[:8] == '[mapend]':
                    print(f'[client][mapend] {data}')
                # if data[:10] == '[mapstart]':
                #     print(f'[client][mapstart] size:{data[10:]}')
                #     data_size = int(data[10:])
                #     received = 0
                #     while received < data_size:
                #         mapdata = self.UDPClientSocket.recv(min(data_size - received, self.bufferSize))
                #         received += len(mapdata)
                #         chunks.append(mapdata)                            
                #         print(f'[client][dlmap] {received} {data_size} {len(mapdata)}')
                #     self.new_map = pickle.load(chunks)
                #     self.got_new_map = True
                #     print(f'[client][new_map] {type(self.new_map)}')
                # else:
                #     print(f'[client] UNKNOWN {data} {data[:10]}')


    def send(self, msg):
        if self.client_id != 0:
            self.UDPClientSocket.sendto(str.encode(msg), self.serverAddressPort)
            time.sleep(0.001)

    def connect_to_server(self):
        print(f'[client][connect_to_server] ... ')
        command = str.encode('[getid]')
        self.UDPClientSocket.sendto(command, self.serverAddressPort)
        time.sleep(0.5)
        dataraw = self.UDPClientSocket.recvfrom(self.bufferSize)
        time.sleep(0.5)
        if not dataraw:
            print(f'[client][connect_to_server] timout ')
            self.connected = False
        else:
            data = dataraw[0].decode()
            if data[:7] == 'yourid:':
                self.client_id = int(data[7:10])
                self.set_id(self.client_id)
                self.connected = True
                print(f'[connect_to_server][gotid] {data} {self.client_id}')

    def send_foo(self):
        command = str.encode('[foobar]')
        # self.UDPClientSocket.sendto(command, self.serverAddressPort)

    def scan_network(self):
        # scan local network for servers
        iplist = [self.ipaddress.split('.')[0] + '.' + self.ipaddress.split('.')[1] + '.' + self.ipaddress.split('.')[2] + '.' + str(k) for k in range(1,255)]

def get_ip_address():
    # returns the 'most real' ip address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]
