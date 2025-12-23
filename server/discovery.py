import socket
import asyncio
import json
from loguru import logger

DISCOVERY_MAGIC = b"BOMBERDUDE_DISCOVERY"

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
        except Exception:
            pass

        # Receive broadcast packets
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        # IMPORTANT for LAN: bind to all interfaces by default.
        # If you bind to 127.0.0.1 you will not receive LAN broadcasts.
        bind_host = getattr(self.bombserver.args, "listen", "0.0.0.0")
        if bind_host in ("127.0.0.1", "localhost", None, ""):
            bind_host = "0.0.0.0"

        sock.bind((bind_host, self.discovery_port))
        logger.info(f"Server discovery listening on {bind_host}:{self.discovery_port}")

        loop = asyncio.get_event_loop()
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
                    players = len(self.bombserver.server_game_state.playerlist)
                except Exception:
                    players = 0

                response = {
                    "type": "server_info",
                    "name": "bombserver",
                    "host": self.bombserver.args.host,
                    "listen": self.bombserver.args.api_listen,
                    "port": self.bombserver.args.port,
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
            except Exception:
                pass
            self._sock = None
            self.running = False

    def stop(self) -> None:
        self.running = False
        # Closing the socket unblocks sock_recvfrom immediately on most platforms
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
