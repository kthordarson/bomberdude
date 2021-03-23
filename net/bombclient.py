import pygame
import random
import socket
import pickle
import time
import datetime
import threading
from threading import Thread
from multiprocessing import  Queue
import os

import sys

def gen_randid(seed=None):
    randid = []
    for k in range(0,7):
        n = random.randint(1,99)
        randid.append(n)
    return randid

class Player():
    def __init__(self):
        self.client_id = ''.join([''.join(str(k)) for k in gen_randid()])

class Game(Thread):
    def __init__(self):
        super(Game, self).__init__()
        self.player = Player()
        self.client = BombClient(server='127.0.0.1', server_port=9999, player=self.player)

class BombClient(Thread):
    def __init__(self,server='127.0.0.1', server_port=9999, player=None):
        super(BombClient, self).__init__()
        self.server = server
        self.server_port = server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player = player
        self.connected = False

    def run(self):
        rawdata = 'donk'
        while self.connected:
            data = pickle.loads(rawdata)
            resp = pickle.dumps(f'[r] got {len(data)}')
            print(resp)
            self.socket.sendall(resp)
            rawdata = self.Receive()

    def Connect(self):
        #print(f'[bcl] id {self.player.client_id} connecting to {self.server} {self.server_port}')
        try:
            self.socket.connect((self.server, self.server_port))
            self.connected = True
            return True
        except Exception as e:
            print(f'[bclient] Err {e}')
            self.connected = False
            return False

    def Send(self, data):
        data = pickle.dumps(data)
        self.socket.sendall(data)

    def Sendpos(self, rawdata):
        posdata = {'x': rawdata.x, 'y': rawdata.y}
        packet = {'auth': self.player.client_id, 'pos':posdata}
        data = pickle.dumps(packet)
        print(f'[sendpos] size {len(data)} p: {packet}')
        try:
            self.socket.sendall(data)
        except ConnectionResetError as e:
            print(f'[sendpos] conn err {e}')
        except WindowsError as e:
            print(f'[sendpos] winerr err {e}')
        except Exception as e:
            print(f'[sendpos] err {e}')

    def _Send(self, rawdata=None):
        if self.connected:
            try:
                # data1 = f'[conn]{self.player.client_id}'
                #data = {'pid' : self.player.client_id, 'rawdata': rawdata}
                data = pickle.dumps(rawdata)
                # print(f'[send] {data}')
                self.socket.sendall(data)
            except Exception as e:
                self.connected = False
                self.authenticated = False
                print(f'[s] ERR {e}')

    def Receive(self):
        try:
            data = self.socket.recv(1024)
            data_rcv = pickle.loads(data)
            return data_rcv
        except Exception as e:
            #self.connected = False
            #self.authenticated = False
            print(f'[r] ERR {e}')
            return None


if __name__ == "__main__":
    print('[bombclient]')
    game = Game()
#    print(f'cl {client}')
    game.client.Connect()
    while True:
        data = {
                'auth': game.player.client_id, 
                'foo' : f'{datetime.datetime.now()}'
                }
        print(f'[send] {data}')
        game.client.Send(data)
        resp = game.client.Receive()
        print(f'[resp] {resp}')
        cmd = input('> ')
        if cmd[:1] == 'q':
            os._exit(0)
        if cmd[:1] == 's':
            data = {
                'auth': game.player.client_id, 
                'foo' : f'donk'
                }
        if cmd[:1] == 'r':
            pass
