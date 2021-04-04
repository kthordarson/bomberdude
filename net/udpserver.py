import pickle
import socket
import threading
import time
import os
from datetime import datetime
class Client:
    def __init__(self, clientid, ipaddress):
        self.clientid = clientid
        self.ipaddress = ipaddress        
    def __repr__(self):
        return self.clientid
    
class UDPServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.clients = []
        self.max_clients = 4

    def configure_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind((self.host, self.port))
        # self.sock.setsockopt(level, optname, value)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_lock = threading.Lock()
        print(f'Server {self.host}:{self.port}...')

    def check_clientid(self, clientid):
        for c in self.clients:
            if c.clientid == clientid:
                return True
        return False
        
    def parse_data(self, data, client_address):
        if len(self.clients) <= self.max_clients:
            client = Client(clientid=data['id'], ipaddress=client_address)
            if self.check_clientid(client.clientid):
                print(f'[parse_data] update clientid: {data["id"]} pos: {data["pos"]}')
            else:
                self.clients.append(client)
                print(f'[parse_data] newclient {client} clientconns: {len(self.clients)}')
            return '[serverok]'
        else:
            print(f'[server] server full clients connected {len(self.clients)} max_clients={self.max_clients} ')
            return '[serverfull]'

    def handle_request(self, data, client_address):
        # print(f'[server] client: {client_address} sent: {data["id"]}')
        clientid = None
        try:
            clientid = data['id']
        except Exception as e:
            print(f'[server] clientid err {e}')
        if clientid:
            resp = self.parse_data(data, client_address)
            self.sock.sendto(resp.encode('utf-8'), client_address)
        #with self.socket_lock:
        #    self.sock.sendto(resp.encode('utf-8'), client_address)
        #    print(f'[slock]')

    def shutdown_server(self):
        self.sock.close()

    def wait_for_client(self):
        data = None
        datapickled = None
        client_address = None
        print(f'[wait_for_client] run: {self.running}')
        while self.running:
            try:
                data, client_address = self.sock.recvfrom(1024)
                datapickled = pickle.loads(data)
            except OSError as err:
                # print(f'[server] oserr {err}')
                datapickled = None
                data = None
            except pickle.UnpicklingError as e:
                print(f'[server] pickle ERR {e}')
                data = None
                datapickled = None
#            except Exception as e:
                # self.running = False
                #print(f'[server] err {e}')
            except KeyboardInterrupt:
                data = None
                datapickled = None
                self.running = False
                self.shutdown_server()
            if datapickled is not None:
                c_thread = threading.Thread(target = self.handle_request, args = (datapickled, client_address))
                c_thread.daemon = True
                c_thread.start()


def main():
    ''' Create a UDP Server and handle multiple clients simultaneously '''
    print(f'[udpmain]')
    udpserver = UDPServer('192.168.1.67', 4444)
    print(f'[udpmain] udpserver {udpserver}')
    udpserver.configure_server()
    s_thread = threading.Thread(target=udpserver.wait_for_client())
    s_thread.daemon = True
    # c_thread.start()
    while True:
        try:
            cmd = input('> ')
            if cmd[:1] == 'q':
                os._exit(0)
            if cmd[:1] == 'r':                
                print(f'[r] {udpserver.running}')
                udpserver.running = True
                print(f'[r] {udpserver.running}')
        except KeyboardInterrupt:
            os._exit(0)

if __name__ == '__main__':
    print('this is udpserver')