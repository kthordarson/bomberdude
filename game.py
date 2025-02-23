import asyncio
import requests
import pygame
import socket
from pygame.math import Vector2 as Vec2d
import math
import json
from queue import Empty

from loguru import logger
from objects import (
    Bomberplayer,
    Bomb,
    BiggerBomb,
    KeysPressed,
    Bullet,
)
from panels import Panel
from utils import get_map_coordinates_rev, gen_randid
from gamestate import GameState
from constants import UPDATE_TICK, PLAYER_MOVEMENT_SPEED, BULLET_SPEED, BULLETDEBUG,GRAPH_HEIGHT, GRAPH_WIDTH, GRAPH_MARGIN, SCREEN_WIDTH, SCREEN_HEIGHT
from camera import Camera

class Bomberdude():
    def __init__(self, args, eventq):
        self.title = "Bomberdude"
        self.args = args
        self.left_pressed = False
        self.right_pressed = False
        self.up_pressed = False
        self.down_pressed = False
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        # self.screen = pygame.display.get_surface()
        self.debug = self.args.debug
        self.manager = None  # Replace with pygame UI manager if needed
        self.t = 0
        self.running = True
        self._gotmap = False
        self.selected_bomb = 1
        self.client_game_state = GameState(args=self.args, name='client')
        self.hitlist = []
        self._connected = False
        self.physics_engine = None
        self.eventq = eventq
        self.draw_graphs = False
        self.poplist = []
        self.netplayers = {}
        self.player_list = []
        self.bomb_list = []
        self.particle_list = []
        self.flame_list = []
        self._show_kill_screen = False
        self.show_kill_timer = 1
        self.show_kill_timer_start = 1
        self.timer = 0
        self.view_bottom = 0
        self.view_left = 0
        self.mouse_pos = Vec2d(x=0, y=0)
        self.background_color = (100, 149, 237)
        self.camera = None  # Replace with pygame camera if needed
        self.guicamera = None  # Replace with pygame camera if needed
        self.sub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.push_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
        map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, map_width, map_height)
        asyncio.create_task(self.do_connect())

    def __repr__(self):
        return f"Bomberdude( {self.title} np: {len(self.client_game_state.players)}  )"

    def connected(self):
        return self._connected

    async def do_connect(self):
        logger.info(f'{self} connecting to sub_sock: {self.sub_sock} ')
        self.sub_sock.connect((self.args.server, 9696))
        logger.info(f'{self} connecting to push_sock: {self.push_sock} ')
        self.push_sock.connect((self.args.server, 9697))
        if self.args.debug:
            logger.debug(f'{self} connecting map: {self._gotmap=}')
        try:
            resp = json.loads(requests.get(f"http://{self.args.server}:9699/get_tile_map").text)
            mapname = resp.get("mapname")
            pos = Vec2d(x=464, y=464)
            position = pos
            logger.debug(f"map {mapname} {pos=} {resp=}")
        except Exception as e:
            logger.error(f"{type(e)} {e=}")
            raise e
        self.client_game_state.load_tile_map(mapname)
        self._gotmap = True
        if self.args.debug:
            logger.debug(f'{self} map: {self._gotmap} conn: {self.connected()} - {self._connected} {pos=}')

        self.bullet_sprite = pygame.image.load("data/bullet0.png")
        self.setup_panels()
        self.setup_labels()
        player_one = Bomberplayer(texture="data/playerone.png", name=self.args.name, client_id=gen_randid(), eventq=self.eventq)
        player_one.position = position
        self.player_list.append(player_one)
        connection_event = {
            "event_time": 0,
            "event_type": "newconnection",
            "client_id": str(player_one.client_id),
            "name": player_one.name,
            "handled": False,
            "handledby": "do_connect",
            "eventid": gen_randid(),
        }
        await self.eventq.put(connection_event)
        self._connected = True
        if self.args.debug:
            logger.debug(f'{self} map: {self._gotmap} conn: {self.connected()} - {self._connected} setup done player {player_one.name} : {player_one.client_id}')
        await asyncio.sleep(1)
        return 1

    def on_show_view(self):
        pass  # self.screen.fill((100, 149, 237))  # GRAY_BLUE equivalent

    def on_hide_view(self):
        pass

    def setup_labels(self):
        self.draw_labels = True
        self.showkilltext = pygame.font.Font(None, 22).render(f"kill: {self.show_kill_timer:.1f}", True, (255, 0, 0))
        self.netplayer_labels = {}

    def setup_panels(self):
        pass  # Implement if needed

    def center_camera_on_player(self, speed=0.2):
        player = self.player_list[0]
        screen_center_x = player.center_x - (SCREEN_WIDTH / 2)
        screen_center_y = player.center_y - (SCREEN_HEIGHT / 2)
        if screen_center_x < 0:
            screen_center_x = 0
        if screen_center_y < 0:
            screen_center_y = 0
        self.camera.position = (screen_center_x, screen_center_y)

    def on_draw(self):
        # self.screen.fill(self.background_color)
        # Draw game elements here
        self.screen.fill((200, 249, 237))
        self.client_game_state.render_map(self.screen, self.camera)
        for player in self.player_list:
            # player.draw(self.screen)
            self.screen.blit(player.image, self.camera.apply(player))
        # for sprite in self.client_game_state.scene:
        #     sprite.draw()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.mouse_pos = Vec2d(x=x, y=y)

    def on_mouse_press(self, x, y, button, modifiers):
        asyncio.create_task(self.handle_on_mouse_press(x, y, button, modifiers))

    async def handle_on_mouse_press(self, x, y, button, modifiers):
        self.mouse_pos = Vec2d(x=x, y=y)
        if button == 1:
            dir_init = self.mouse_pos
            length = math.hypot(*dir_init)
            dir = (dir_init[0] / length, dir_init[1] / length)
            bullet_angle = math.degrees(math.atan2(-dir[1], dir[0]))
            bullet_vel = Vec2d(x=dir[0], y=dir[1])
            bulletpos = self.mouse_pos
            event = {
                "event_time": 0,
                "event_type": "bulletfired",
                "bullet_vel": bullet_vel,
                "shooter": 0,
                "pos": bulletpos,
                "ba": bullet_angle,
                "timer": 3515,
                "handled": False,
                "handledby": "kremer",
                "eventid": gen_randid(),
            }
            await self.eventq.put(event)
            logger.debug(f'eventq: {self.eventq.qsize()} {dir_init=} {dir=} {bullet_angle=} {bullet_vel=} {length=}  {x=} {y=}')
        else:
            logger.warning(f"{x=} {y=} {button=} {modifiers=}")
            return

    def xon_key_press(self, key):
        # key = pygame.key.get_pressed()
        pass  # asyncio.create_task(self.handle_on_key_press(key))

    def xon_key_release(self, key):
        # key = pygame.key.get_pressed()
        pass  # asyncio.create_task(self.handle_on_key_release(key))

    def handle_on_key_press(self, key):
        key_ = pygame.key.get_pressed()
        if key == pygame.K_1:
            self.selected_bomb = 1
        elif key == pygame.K_2:
            self.selected_bomb = 2
        elif key == pygame.K_F1:
            self.debug = not self.debug
            logger.debug(f"debug: {self.debug}")
        elif key == pygame.K_F2:
            self.client_game_state.debug = not self.client_game_state.debug
            logger.debug(f"gsdebugmode: {self.client_game_state.debug} debug: {self.debug}")
        elif key == pygame.K_F3:
            pass
        elif key == pygame.K_F4:
            self.draw_graphs = not self.draw_graphs
        elif key == pygame.K_F5:
            pass
        elif key == pygame.K_F6:
            self.draw_labels = not self.draw_labels
        elif key == pygame.K_F7:
            pygame.display.toggle_fullscreen()
        elif key == pygame.K_ESCAPE or key == pygame.K_q or key == 27:
            self._connected = False
            self.running = False
            logger.warning("quit")
            # pygame.display.quit()
            # pygame.quit()
            return
        elif key == pygame.K_UP or key == pygame.K_w or key == 119:
            self.player_list[0].change_y = -PLAYER_MOVEMENT_SPEED
            self.up_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
            logger.debug(f'{key=}')
        elif key == pygame.K_DOWN or key == pygame.K_s or key == 115:
            self.player_list[0].change_y = PLAYER_MOVEMENT_SPEED
            self.down_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
            logger.debug(f'{key=}')
        elif key == pygame.K_LEFT or key == pygame.K_a or key == 97:
            self.player_list[0].change_x = -PLAYER_MOVEMENT_SPEED
            self.left_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
            logger.debug(f'{key=}')
        elif key == pygame.K_RIGHT or key == pygame.K_d or key == 100:
            self.player_list[0].change_x = PLAYER_MOVEMENT_SPEED
            self.right_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
            logger.debug(f'{key=}')

    def handle_on_key_release(self, key):
        # key = pygame.key.get_pressed()
        # logger.info(f'{key=}')
        if key == pygame.K_UP or key == pygame.K_w:
            self.player_list[0].change_y = 0
            self.up_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == pygame.K_DOWN or key == pygame.K_s:
            self.player_list[0].change_y = 0
            self.down_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == pygame.K_LEFT or key == pygame.K_a:
            self.player_list[0].change_x = 0
            self.left_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == pygame.K_RIGHT or key == pygame.K_d:
            self.player_list[0].change_x = 0
            self.right_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        if key == pygame.K_SPACE:
            pass  # _ = [k.dropbomb(self.selected_bomb) for k in self.player_list]
        self.client_game_state.keys_pressed.keys[key] = False
        # await asyncio.sleep(0.1)

    def handle_game_events(self, game_events):
        logger.debug(f'{game_events=}')

    async def update(self):
        self.timer += 1 / 60
        # logger.debug(f'{self=}')
        for player in self.player_list:
            player.update(self.client_game_state.collidable_tiles)
            self.camera.update(player)
            # logger.debug(f'{player} {player.position=}')
            # player.draw(self.screen)
        if not self._gotmap:
            if self.args.debug:
                logger.warning(f"{self} no map!")
            await asyncio.sleep(0.5)
            # return
        try:
            events = await self.client_game_state.event_queue.get_nowait()
            await self.handle_game_events(events)
            # self.client_game_state.event_queue.task_done()
        except (Empty, asyncio.queues.QueueEmpty):
            pass
        # self.update_netplayers()
        # self.update_poplist()
        # self.center_camera_on_player()
