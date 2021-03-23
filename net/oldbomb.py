class BombServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.running = True
        self.kill = False
        self.conn_list = []
        self.threads = []
        self.clients = {}
        self.data_bombers = []
        self.HOST = '0.0.0.0'
        self.PORT = 9999
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(5)

    def self_kill(self):
        self.kill = True
        self.running = False

    def GameSession(self, Connections=None, conn=None, auth=None):

        while self.running:
            if self.kill:
                print(f'[GS] kill')
                self.running = False
                self.socket.close()
                return
            
            try:
                for k in Connections:
                    if k:
                        d = k.recv(1024)
                        if d:
                            self.data_bombers.append(d)
                # data_bomber = Connections[1].recv(1024)
                # print(f'[bserver] {data_bomber}')
            except ConnectionError as conn_err:
                print(f'[bserver] ConnectionError {conn_err}')
            except KeyboardInterrupt as key_err:
                print(f'[bserver] KeyboardInterrupt {key_err}')
                break
            except IndexError as ind_err:
                print(f'[bserver] indx err {ind_err} {Connections}')
            #data_bomber_2 = Connections[1].recv(1024)
            if not self.data_bombers:
                return
            else:
                for data_bomber_raw in self.data_bombers:
                    # print(f'[gs] b {len(self.data_bombers)}')
                    try:
                        data_bomber = pickle.loads(data_bomber_raw)
                    except Exception as e:
                        print(f'[bserver] pickle {e} data {data_bomber_raw}')
                        # print(f'[bserver] data {data_bomber_raw}')
                        data_bomber = 'None'
                        return
                    # print(f'{data_bomber}')
                    if 'auth' in data_bomber:
                        # print('a')
                        idcheck = data_bomber['auth']
                        auth = idcheck
                        resp = {'resp': 'ok'}
                        data = pickle.dumps(resp)
                        [k.sendall(data) for k in Connections]
                        # Connections[0].sendall(data)
                        self.clients[idcheck] = 'auth'
                        # print(f'[bserver] a: {auth} p: {data_bomber} ld: {len(data_bomber)} ld1: {len(data_bomber_raw)} cl: {len(self.clients)}')
                        if 'pos' in data_bomber:                            
                            if data_bomber['auth'] in self.clients:
                                # print(f'[pos] {data_bomber["auth"]} {data_bomber["pos"]}')
                                resp = {'resp': 'ok'}
                                data = pickle.dumps(resp)
                                [k.sendall(data) for k in Connections]
                                # Connections[0].sendall(data)
                            else:
                                print(f'[GS] poserr {data_bomber} {data_bomber}')
                    else:
                        pass
                        # print(f'[GS] error {data_bomber} {data_bomber}')
        self.socket.close()
    def run(self):
        self.running = True
        # self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.socket.bind((self.HOST, self.PORT))
        # self.socket.listen(5)
        print(f'[bserver run]')

        while self.running:
            if self.kill:
                print(f'[bserver kill]')
                return
            for i in range(4):
                if i:
                    print(f'[bs] waiting for player i: {i}')
                try:
                        conn, addr = self.socket.accept()
                except KeyboardInterrupt as e:
                    print(f'[bserver] {e} i: {i}')
                    self.running = False
                    self.kill = True
                    return
                except OSError as e:
                    print(f'[bserver] OS {e} {conn} i: {i}')
                    # self.running = False
                    # self.kill = True
                    return
                except TypeError as e:
                    print(f'[bserver] T {e} {conn} i: {i}')
                except Exception as e:
                    print(f'[bserver] EX {e} {conn}i: {i} ')
                finally:
                    print(f'[bserver] {addr[0]} connected i: {i}')
                    self.conn_list.append(conn)
                    print(f'[bserver] OK {conn} i: {i} ')
                    self.threads.append(threading.Thread(target=self.GameSession, args=(self.conn_list,)))
                    self.threads[-1].start()

                    # gs = self.GameSession(Connections=self.conn_list)
                    # gs.start()
                    # self.conn_list = []


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
