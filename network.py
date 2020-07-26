# netstuff
import socket
import os
import time
from threading import Thread, Event
import asynchat, asyncore
from rencode import loads, dumps
import pickle
import random

class Server(Thread):
    def __init__(self):
        super(Server, self).__init__()
        self.localIP = '127.0.0.1'
        self.localPort = 10102
        self.bufferSize = 1024
        self.listening = False
        # self.msgFromServer = "Hello UDP Client"
        # self.bytesToSend = str.encode(self.msgFromServer)
        self.foobar = str.encode('foobar')
        self.clients = []
        self.connections = 0
        self._stop_event = Event()

    def get_player_id(self, client):
        if self.connections <= 3:
            id = str(random.randint(30,99))
            self.bytesToSend = str.encode('yourid:' + id)
            self.UDPServerSocket.sendto(self.bytesToSend, client)
            self.connections += 1
            return id
        else:
            id = 0
            self.bytesToSend = str.encode('yourid:' + id)
            self.UDPServerSocket.sendto(self.bytesToSend, client)
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
                    if command == 'getid':
                        print(f'[server][gotdata] {data}')
                        self.get_player_id(data[1])
                    if command[:7] == '[event]':
                        print(f'[server][gotdata] {data}')
                    if command[:11] == '[playerpos]':
                        print(f'[server][gotdata] {data}')
            except Exception as e:
                print(f'[server][err] {e}')


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
        #self.bufferSize = 1024
        self.connected = False
        self.hostname = socket.gethostname()
        self.ipaddress = socket.gethostbyname(self.hostname)
        self.client_id = 0

    def create_socket(self):
        try:
            self.UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            # self.UDPClientSocket.bind(self.serverAddressPort)
            self.got_socket = True
            print(f'[client] socket created: {self.UDPClientSocket}')
        except Exception as e:
            print(f'[client] exception {e}')
            self.connected = False
            self.got_socket = False

    def set_id(self, id):
        print(f'[client][set_id] old {self.client_id} new {id}')
        self.client_id = id

    def run(self):
        # self.connect_to_server()
        while True and self.client_id != 0:
            try:
                dataraw = self.UDPClientSocket.recvfrom(self.bufferSize)                
                if not dataraw:
                    break
                else:
                    data = dataraw[0].decode()
                    if data[:7] == 'yourid:':
                        self.client_id = int(data[7:10])
                        self.set_id(self.client_id)
                        self.connected = True
                        print(f'[client][gotdata] {data} {self.client_id}')
            except Exception as e:
                print(f'[client][err] {e}')


    def send(self, msg):
        if self.client_id != 0:
            self.UDPClientSocket.sendto(str.encode(msg), self.serverAddressPort)
            time.sleep(0.001)

    def connect_to_server(self):
        command = str.encode('getid')
        self.UDPClientSocket.sendto(command, self.serverAddressPort)


