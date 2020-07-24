# netstuff
import socket
class Server():
    def __init__(self):
        self.localIP = '127.0.0.1'
        self.localPort = 10101
        self.bufferSize = 1024
        self.listening = False
        self.msgFromServer = "Hello UDP Client"
        self.bytesToSend = str.encode(self.msgFromServer)
    def create_socket(self):
        self.UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.UDPServerSocket.bind((self.localIP, self.localPort))
        print(f'Server listening')

    def get_data(self):
        if self.listening:
            while(True):                
                bytesAddressPair = self.UDPServerSocket.recvfrom(bufferSize)
                message = bytesAddressPair[0]
                address = bytesAddressPair[1]
                clientMsg = "Message from Client:{}".format(message)
                clientIP  = "Client IP Address:{}".format(address)
                print(clientMsg)
                print(clientIP)

                self.UDPServerSocket.sendto(bytesToSend, address)            


    
