import socket
import pickle
import random
import threading
from threading import Thread
from multiprocessing import  Queue
import os
import sys
from ctypes import WinError

def get_ip():
    return '0.0.0.0'

class BombServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.running = True
        self.kill = False
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(0)
    server.bind(('localhost', 50000))
    server.listen(5)
    inputs = [server]
    outputs = []
    message_queues = {}
    def run(self):
        while inputs:
            readable, writable, exceptional = select.select(inputs, outputs, inputs)
            for s in readable:
                if s is server:
                    connection, client_address = s.accept()
                    connection.setblocking(0)
                    inputs.append(connection)
                    message_queues[connection] = Queue.Queue()
                else:
                    data = s.recv(1024)
                    if data:
                        message_queues[s].put(data)
                        if s not in outputs:
                            outputs.append(s)
                    else:
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]

        for s in writable:
            try:
                next_msg = message_queues[s].get_nowait()
            except Queue.Empty:
                outputs.remove(s)
            else:
                s.send(next_msg)

        for s in exceptional:
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()
            del message_queues[s]

    def Stop(self):
        self.socket.close()
        self.running = False

    def clean_exit(self, threads):
        for t in threads:
            t.join()

    def stopmain(self, maint):
        self.Stop()
        for k in self.threads:
            print(f'[stopmain] {k} {self.running} {self.kill} ')
            # k.self_kill()
        print(f'[stopmain] {self.running} {self.kill}')
        self.running = False
        print(f'[stopmain] r {self.running} {self.kill}')
        self.kill = True
        print(f'[stopmain] k {self.running} {self.kill}')
        # maint.self_kill()
        # maint.join()
        print(f'[stopmain] j {self.running} {self.kill}')
        # print(f'[stopmain] join')
        os._exit(0)

    def check_threads(self, threads):
        return True in [t.isAlive() for t in threads]

    def check_main_thread(self, thread):
        return thread.isAlive()

    def reset_threads(self, threads):
        print(f'RESET')
        for t in threads:
            t.join()



if __name__ == "__main__":
    print('[bombserver]')
    server = BombServer()
#    print(f'{server}')
    #server_thread = threading.Thread(target=server.Start, args=())
    #server_thread = threading.Thread(target=server.Start, args=())
    server.start()
    while server.is_alive():
        try:
            cmd = input('> ')
            if cmd[:1] == 'r':
                pass
            if cmd[:1] == 's':
                print(f'[server] t: {len(server.threads)}  c: {len(server.conn_list)}')
            if cmd[:1] == 'q':
                server.stopmain(server)
        except KeyboardInterrupt:
            server.stopmain(server)

    #app = QApplication(sys.argv)
    #window = ServerWindow()
    #window.show()
    #app.exec_()
