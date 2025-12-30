import sys
import socket
import asyncio
import json
from loguru import logger

DISCOVERY_MAGIC = b"BOMBERDUDE_DISCOVERY"

def get_local_ip_addresses():
    ips = set()
    for iface in socket.if_nameindex():
        iface_name = iface[1]
        try:
            for fam, _, _, _, sockaddr in socket.getaddrinfo(None, 0, family=socket.AF_INET, proto=socket.IPPROTO_UDP):
                s = socket.socket(fam, socket.SOCK_DGRAM)
                try:
                    s.connect(('8.8.8.8', 80))
                    ip = s.getsockname()[0]
                    if not ip.startswith("127."):
                        ips.add(ip)
                except Exception:
                    pass
                finally:
                    s.close()
        except Exception:
            pass
    return list(ips)

class ServerDiscovery:
    def __init__(self, bombserver, discovery_port: int = 12345):
        self.bombserver = bombserver
        self.discovery_port = discovery_port
        self.running = False
        self._sock: socket.socket | None = None

    async def start_discovery_service(self) -> None:
        """Listen for UDP broadcast discovery packets and respond with server info.

        Client sends UDP broadcast payload: b'BOMBERDUDE_DISCOVERY'
        Server responds with JSON: {type,name,port,players,map}
        """
        self.running = True

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock = sock

        # Allow quick restarts / multiple listeners on some platforms
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception as e:
            logger.error(f"Failed to set SO_REUSEPORT: {e} {type(e)}")

        # Receive broadcast packets
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        # IMPORTANT for LAN: bind to all interfaces by default.
        # If you bind to 127.0.0.1 you will not receive LAN broadcasts.
        bind_host = get_local_ip_addresses()[0]
        sock.bind((bind_host, self.discovery_port))
        logger.info(f"Server discovery listening on {bind_host}:{self.discovery_port}")

        loop = asyncio.get_running_loop()
        try:
            while self.running:
                try:
                    # Timeout so stop() can break promptly
                    data, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 1024), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                except (OSError, asyncio.CancelledError):
                    break

                if not data:
                    continue

                if data.strip() != DISCOVERY_MAGIC:
                    continue

                try:
                    players = len(self.bombserver.game_state.playerlist)
                except Exception as e:
                    logger.error(f"Error getting player count: {e} {type(e)}")
                    players = 0

                response = {
                    "type": "server_info",
                    "name": "bombserver",
                    "listen": self.bombserver.args.listen,
                    "api_port": self.bombserver.args.api_port,
                    "server_port": self.bombserver.args.server_port,
                    "players": players,
                    "map": self.bombserver.args.mapname,
                }

                try:
                    sock.sendto(json.dumps(response).encode("utf-8"), addr)
                    # logger.debug(f"Discovery response sent to {addr}: {response}")
                except Exception as e:
                    logger.error(f"Failed sending discovery response to {addr}: {e}")
        finally:
            try:
                sock.close()
            except Exception as e:
                logger.error(f"Error closing discovery socket: {e} {type(e)}")
            self._sock = None
            self.running = False

    def stop(self) -> None:
        self.running = False
        # Closing the socket unblocks sock_recvfrom immediately on most platforms
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as e:
                logger.error(f"Error closing discovery socket: {e} {type(e)}")
                pass
            self._sock = None
