import socket
import asyncio
import json
from loguru import logger

class ServerDiscovery:
    def __init__(self, bombserver, discovery_port=12345):
        self.bombserver = bombserver
        self.discovery_port = discovery_port
        self.running = False

    async def start_discovery_service(self):
        """Listen for UDP broadcast discovery packets"""
        self.running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bombserver, self.discovery_port))
        sock.setblocking(False)

        logger.info(f"Server discovery service listening on port {self.discovery_port}")

        while self.running:
            try:
                data, addr = await asyncio.get_event_loop().sock_recvfrom(sock, 1024)
                msg = data.decode('utf-8')
                if msg == 'BOMBERDUDE_DISCOVERY':
                    # Send server info
                    response = {
                        'type': 'server_info',
                        'name': 'bombserver',  # self.bombserver.args.name,
                        'port': self.bombserver.args.port,
                        'players': len(self.bombserver.server_game_state.playerlist),
                        'map': self.bombserver.args.mapname
                    }
                    sock.sendto(json.dumps(response).encode('utf-8'), addr)
                    logger.debug(f"Sent discovery response to {addr}")
            except Exception as e:
                if not isinstance(e, BlockingIOError):
                    logger.error(f"Discovery service error: {e}")
                await asyncio.sleep(0.1)

    def stop(self):
        self.running = False
