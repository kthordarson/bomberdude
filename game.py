import asyncio
import requests
# import zmq
# from zmq.asyncio import Context
import socket
from pymunk import Vec2d
import math
import json
from queue import Empty
import arcade
from arcade import get_window
from arcade import draw_line
from arcade.gui import (
    UIAnchorLayout,
    UIGridLayout,
    UIManager,
)
from arcade.math import (
    get_angle_degrees,
)
from loguru import logger
from objects import (
    Bomberplayer,
    Bomb,
    BiggerBomb,
    KeysPressed,
    UIPlayerLabel,
    Bullet,
)
from panels import Panel
from utils import get_map_coordinates_rev, gen_randid
from gamestate import GameState
from constants import UPDATE_TICK, PLAYER_MOVEMENT_SPEED, BULLET_SPEED, BULLETDEBUG,GRAPH_HEIGHT, GRAPH_WIDTH, GRAPH_MARGIN, SCREEN_WIDTH, SCREEN_HEIGHT

class Bomberdude(arcade.View):
    def __init__(self, args, eventq):
        super().__init__()
        self.title = "Bomberdude"
        self.args = args
        self.left_pressed = False
        self.right_pressed = False
        self.up_pressed = False
        self.down_pressed = False
        self.window = get_window()
        self.debug = self.args.debug
        self.manager = UIManager()
        # self.window.center_window() # set_location(0,0)
        # self.window.width = self.window.width
        # self.window.height = self.window.height
        self.t = 0
        self._gotmap = False
        self.selected_bomb = 1
        self.client_game_state = GameState(args=self.args, name='client')
        self.hitlist = []
        # self.ioctx = Context.instance()
        # self.ioctx.socket(zmq.SUB)  # : Socket
        # self.data_sock: Socket = self.ioctx.socket(zmq.SUB)
        # self.ioctx.socket(zmq.PUSH)  # : Socket
        self._connected = False
        self.physics_engine = None
        self.eventq = eventq  # Queue()
        self.draw_graphs = False
        self.poplist = []
        self.netplayers = {}
        self.player_list = arcade.SpriteList()
        self.bomb_list = arcade.SpriteList(use_spatial_hash=True)
        # self.bullet_list = arcade.SpriteList(use_spatial_hash=True)
        self.particle_list = arcade.SpriteList(use_spatial_hash=True)
        self.flame_list = arcade.SpriteList(use_spatial_hash=True)
        self._show_kill_screen = False
        self.show_kill_timer = 1
        self.show_kill_timer_start = 1
        self.timer = 0
        self.view_bottom = 0
        self.view_left = 0
        self.mouse_pos = Vec2d(x=0, y=0)
        self.camera = arcade.Camera2D()
        self.guicamera = arcade.Camera2D()
        self.sub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.push_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __repr__(self):
        return f"Bomberdude( {self.title} np: {len(self.client_game_state.players)}  )"

    def connected(self):
        return self._connected

    def show_kill_screen(self):
        self.show_kill_timer -= 1 / UPDATE_TICK
        self.window.set_caption(f"{self.title} killed {self.show_kill_timer:.1f}")
        if self.show_kill_timer <= 0:
            self._show_kill_screen = False
            self.window.set_caption(f"{self.title} respawned")
        return self._show_kill_screen

    async def do_connect(self):
        logger.info(f'{self} connecting to sub_sock: {self.sub_sock} ')
        self.sub_sock.connect((self.args.server, 9696))
        logger.info(f'{self} connecting to push_sock: {self.push_sock} ')
        self.push_sock.connect((self.args.server, 9697))
        # self.sub_sock.connect(f"tcp://{self.args.server}:9696")
        # self.sub_sock.subscribe("")
        # self.push_sock.connect(f"tcp://{self.args.server}:9697")
        self.window.set_caption(f"{self.title} connecting to {self.args.server} ")
        if self.debug:
            logger.debug(f'{self} connecting map: {self._gotmap=}')
        # get tilemap and scene from server
        try:
            resp = json.loads(requests.get(f"http://{self.args.server}:9699/get_tile_map").text)
            mapname = resp.get("mapname")
            pos = Vec2d(x=464,y=464)  # resp.get("position")
            position = pos  # Vec2d(x=123,y=23)  # Vec2d(x=pos[0], y=pos[1])
            logger.debug(f"map {mapname} {pos=} {resp=}")
        except Exception as e:
            logger.error(f"{type(e)} {e=}")
            raise e
            # mapname = "data/maptest5.json"
            # pos = (110, 110)
            # position = Vec2d(x=pos[0], y=pos[1])
        self.client_game_state.load_tile_map(mapname)
        self._gotmap = True
        # resp = requests.get(f'http://{self.args.server}:9699/get_position')
        # pos = resp.text
        if self.debug:
            logger.debug(f'{self} map: {self._gotmap} conn: {self.connected()} - {self._connected} {pos=}')
        self.background_color = arcade.color.BLACK
        self.bullet_sprite = arcade.load_texture("data/bullet0.png")
        self.setup_panels()
        self.setup_labels()
        self.client_game_state.scene.add_sprite_list("static")
        self.client_game_state.scene["static"].sprite_list.extend(self.client_game_state.tile_map.sprite_lists["Blocks"])
        self.client_game_state.scene["static"].sprite_list.extend(self.client_game_state.tile_map.sprite_lists["Walls"])
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
        if self.debug:
            logger.debug(f'{self} map: {self._gotmap} conn: {self.connected()} - {self._connected} setup done player {player_one.name} : {player_one.client_id}')
        self.window.set_caption(f"{self.title} connected {self.args.server} ")
        self.manager.enable()
        await asyncio.sleep(1)
        return 1

    def on_show_view(self):
        self.window.background_color = arcade.color.GRAY_BLUE
        self.manager.enable()

    def on_hide_view(self):
        pass  # self.manager.disable()

    def setup_labels(self):
        self.draw_labels = True
        self.showkilltext = arcade.Text(f"kill: {self.show_kill_timer:.1f}", 100, 100, arcade.color.RED, 22)
        self.netplayer_labels = {}

    def setup_panels(self):
        # self.manager_visible = True
        # self.grid = UIGridLayout(x=123,y=123,column_count=2, row_count=3, vertical_spacing=5)
        self.grid = self.manager.add(UIGridLayout(column_count=4, row_count=4, vertical_spacing=5, align_horizontal="center", align_vertical="center", size_hint=(26, 27),))
        # gridsb = self.grid.add(self.startbtn, col_num=0, row_num=0)
        # font_size = 12
        # pos = font_size * 2
        # sy = self.window.height - pos
        # sx = self.window.width - 100
        self.netplayer_grid = UIGridLayout(x=23, y=23, size_hint=(144, 178), column_count=6, row_count=6, vertical_spacing=6, horizontal_spacing=6, align_horizontal="center", align_vertical="center",)
        self.anchor = self.manager.add(UIAnchorLayout(x=4, y=4, anchor_x="left", anchor_y="bottom"))  # , anchor_y='top'))
        self.anchor.add(child=self.netplayer_grid)
        self.panel = Panel(10, 10, 250, 50, self.window)

    def center_camera_on_player(self, speed=0.2):
        player = self.player_list[0]  # Assuming the first player in the list is the main player
        screen_center_x = player.center_x - (self.camera.viewport_width / 2)
        screen_center_y = player.center_y - (self.camera.viewport_height / 2)
        if screen_center_x < 0:
            screen_center_x = 0
        if screen_center_y < 0:
            screen_center_y = 0
        # player_centered = (screen_center_x, screen_center_y)
        # self.camera.move(player_centered, speed)
        self.camera.position = (screen_center_x, screen_center_y)

    def on_draw(self):
        if not self._gotmap:
            return
        self.camera.use()
        self.clear()
        self.client_game_state.scene["Background"].draw()
        self.client_game_state.scene["Walls"].draw()
        self.client_game_state.scene["Blocks"].draw()
        self.client_game_state.scene["Bullets"].draw()
        self.client_game_state.scene["Bombs"].draw()
        self.client_game_state.scene["Flames"].draw()
        self.client_game_state.scene["Particles"].draw()
        self.client_game_state.scene["Upgrades"].draw()
        self.client_game_state.scene["Netplayers"].draw()
        self.manager.draw()
        # if self.manager_visible:
        #    self.manager.draw()
        self.guicamera.use()
        # self.panel.draw()
        self.player_list.draw()
        # self.center_camera_on_player()

        if self._show_kill_screen:
            self.guicamera.use()
            self.show_kill_screen()
            # self.show_kill_timer = self.show_kill_timer_start-time.time()
            self.showkilltext.value = f"kill: {self.show_kill_timer:.1f}"
            self.showkilltext.draw()
        if self.debug:
            self.on_draw_debug()
        # if self.draw_labels:
        # 	for label in self.labels:
        # 		label.draw()

    def on_draw_debug(self):
        if BULLETDEBUG:
            for b in self.client_game_state.scene["Bullets"]:
                if b.can_kill:
                    self.camera.use()
                    # draw_line(start_x=b.center_x, start_y=b.center_y, end_x=self.playerone.center_x, end_y=self.playerone.center_y, color=arcade.color.ORANGE, line_width=1, )
                    textpos = get_map_coordinates_rev(b.position, self.camera)
                    self.guicamera.use()
                    try:
                        textpos += Vec2d(10, 0)
                        arcade.Text(text=f"bxc: {b.change_x:.2f} bcy: {b.change_y:.2f} ", start_x=int(textpos.x), start_y=int(textpos.y), color=arcade.color.BLACK, font_size=10, ).draw()
                        textpos += Vec2d(0, 11)
                        arcade.Text(text=f"ba: {b.angle:.2f}", start_x=int(textpos.x), start_y=int(textpos.y), color=arcade.color.BLACK, font_size=10,).draw()
                    except AttributeError as e:
                        logger.error(f"{e} textpos={textpos} {b=}")

    def send_key_press(self, key, modifiers):  # todo
        ...

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.mouse_pos = Vec2d(x=x, y=y)

    def flipyv(self, v):
        return Vec2d(x=int(v.x), y=int(-v.y + self.window.height))

    def on_mouse_press(self, x, y, button, modifiers):
        asyncio.create_task(self.handle_on_mouse_press(x, y, button, modifiers))

    async def handle_on_mouse_press(self, x, y, button, modifiers):
        self.mouse_pos = Vec2d(x=x, y=y)
        if button == 1:
            dir_init = self.mouse_pos  # (x-self.playerone.position[0], y-self.playerone.position[1])
            length = math.hypot(*dir_init)
            dir = (dir_init[0] / length, dir_init[1] / length)
            bullet_angle = math.degrees(math.atan2(-dir[1], dir[0]))
            # change_x = 1 - math.cos(bullet_angle) * BULLET_SPEED
            # change_y = math.sin(bullet_angle) * BULLET_SPEED
            bullet_vel = Vec2d(x=dir[0], y=dir[1])
            bulletpos = self.mouse_pos  # Vec2d(x=self.playerone.center_x, y=self.playerone.center_y)
            event = {
                "event_time": 0,
                "event_type": "bulletfired",
                "bullet_vel": bullet_vel,
                "shooter": 0,  # self.playerone.client_id,
                "pos": bulletpos,  # bullet.position,
                "ba": bullet_angle,
                "timer": 3515,
                "handled": False,
                "handledby": "kremer",  # self.playerone.client_id,
                "eventid": gen_randid(),
            }
            await self.eventq.put(event)
            logger.debug(f'eventq: {self.eventq.qsize()} {dir_init=} {dir=} {bullet_angle=} {bullet_vel=} {length=}  {x=} {y=}')
        else:
            logger.warning(f"{x=} {y=} {button=} {modifiers=}")
            return

    def on_key_press(self, key, modifiers):
        asyncio.create_task(self.handle_on_key_press(key, modifiers))

    async def handle_on_key_press(self, key, modifiers):
        # todo check collisions before sending keypress...
        # sendmove = False
        if len(self.player_list) == 0:
            return
        if self.debug:
            logger.info(f'{key=} {modifiers=} ')
            # logger.debug(f'{self.client_game_state.to_json()}')
        # if self.playerone.killed:
        #   logger.warning("playerone killed")
            # return
        # logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
        if key == arcade.key.KEY_1:
            self.selected_bomb = 1
        elif key == arcade.key.KEY_2:
            self.selected_bomb = 2
        elif key == arcade.key.F1:
            self.debug = not self.debug
            logger.debug(f"debug: {self.debug}")
        elif key == arcade.key.F2:
            self.client_game_state.debug = not self.client_game_state.debug
            logger.debug(f"gsdebugmode: {self.client_game_state.debug} debug: {self.debug}")
        elif key == arcade.key.F3:
            pass  # debug_dump_game(self)
        elif key == arcade.key.F4:
            self.draw_graphs = not self.draw_graphs
        elif key == arcade.key.F5:
            arcade.clear_timings()
        elif key == arcade.key.F6:
            self.draw_labels = not self.draw_labels
        elif key == arcade.key.F7:
            self.window.set_fullscreen(not self.window.fullscreen)
            # width, height = self.window.get_size()
            self.window.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
            self.camera = arcade.Camera(viewport=(0, 0, self.window.width, self.window.height))
        # elif key == arcade.key.TAB:
        #   self.manager_visible = not self.manager_visible
        elif key == arcade.key.ESCAPE or key == arcade.key.Q:
            self._connected = False
            quitevent = {
                "event_time": 0,
                "event_type": "playerquit",
                "client_id": 0,  # self.playerone.client_id,
                "eventid": gen_randid(),
            }
            await self.eventq.put(quitevent)  # todo fix
            logger.warning("quit")
            arcade.close_window()
            return

        # TODO get local client to send keys
        elif key == arcade.key.UP or key == arcade.key.W:
            # self.playerone.change_y = PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_y = PLAYER_MOVEMENT_SPEED
            self.up_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
        elif key == arcade.key.DOWN or key == arcade.key.S:
            # self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_y = -PLAYER_MOVEMENT_SPEED
            self.down_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
        elif key == arcade.key.LEFT or key == arcade.key.A:
            # self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_x = -PLAYER_MOVEMENT_SPEED
            self.left_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            # self.playerone.change_x = PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_x = PLAYER_MOVEMENT_SPEED
            self.right_pressed = True
            self.client_game_state.keys_pressed.keys[key] = True
            # self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})

    def on_key_release(self, key, modifiers):
        # TODO get local client to send keys
        if len(self.player_list) == 0:
            return
        if key == arcade.key.UP or key == arcade.key.W:
            # self.playerone.change_y = PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_y = 0
            self.up_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == arcade.key.DOWN or key == arcade.key.S:
            # self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_y = 0
            self.down_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == arcade.key.LEFT or key == arcade.key.A:
            # self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_x = 0
            self.left_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            # self.playerone.change_x = PLAYER_MOVEMENT_SPEED
            [k for k in self.player_list][0].change_x = 0
            self.right_pressed = False
            self.client_game_state.keys_pressed.keys[key] = False
            # self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})
        if (
            key == arcade.key.UP
            or key == arcade.key.DOWN
            or key == arcade.key.W
            or key == arcade.key.S
        ):
            [k for k in self.player_list][0].change_y = 0
            # self.playerone.change_y = 0
        elif (
            key == arcade.key.LEFT
            or key == arcade.key.RIGHT
            or key == arcade.key.A
            or key == arcade.key.D
        ):
            [k for k in self.player_list][0].change_x = 0  # self.playerone.change_x = 0
        elif key == arcade.key.SPACE:
            _ = [k.dropbomb(self.selected_bomb) for k in self.player_list]  # self.playerone.dropbomb(self.selected_bomb, self.eventq)
        self.client_game_state.keys_pressed.keys[key] = False

    def handle_game_events(self, game_event):
        # gspcopy = copy.copy(self.client_game_state.game_events)
        # [self.client_game_state.game_events.remove(game_event) for game_event in self.client_game_state.game_events if game_event.get('handled')]
        if not self._gotmap:
            self.setup_network()
        # for game_event in game_events:
        # game_event = game_events.get("game_events")
        event_type = game_event.get("event_type")
        gameevent_clid = game_event.get("client_id")
        if self.debug:
            logger.info(f'gameevent_clid: {gameevent_clid} {event_type=} {game_event=} ')
        match event_type:
            case "extrabomb":
                logger.info(f"{event_type=} {game_event=}")
            case "extrahealth":
                # extrahealth = game_event.get("amount")
                logger.info(f"{event_type=} {game_event=}")
            case "playerquit":
                try:
                    l0 = len(self.netplayers)
                    self.netplayers[gameevent_clid].remove_from_sprite_lists()
                    self.netplayers.pop(gameevent_clid)
                    self.netplayer_labels.pop(gameevent_clid)
                    self.client_game_state.players.pop(gameevent_clid)
                    # self.netplayers.pop(self.netplayers[clid])
                    logger.debug(
                        f"{event_type} from {gameevent_clid} {l0} -> {len(self.netplayers)}"
                    )
                except KeyError as e:
                    logger.warning(f"{e} {gameevent_clid=} {self.netplayers=}")
                except Exception as e:
                    logger.error(f"{type(e)} {e} {gameevent_clid=} {self.netplayers=}")
            case "ackrespawn":
                [
                    self.netplayers[k].set_texture(
                        arcade.load_texture("data/netplayer.png")
                    )
                    for k in self.netplayers
                    if k == gameevent_clid
                ]  # [0]
                logger.debug(f"{event_type} from {gameevent_clid}")
                # if clid == self.playerone.client_id:
                #    self.playerone.respawn()
            case "upgradeblock":
                upgradetype = game_event.get("upgradetype")
                blkpos = Vec2d(
                    x=game_event.get("fpos")[0], y=game_event.get("fpos")[1]
                )
                newblk = self.client_game_state.create_upgrade_block(upgradetype, blkpos)
                self.client_game_state.scene.add_sprite("Upgrades", newblk)
                if self.debug:
                    logger.info(
                        f"{event_type} upgradetype {game_event.get('upgradetype')} {newblk}"
                    )
            case "acknewconn":
                name = game_event.get("name", "missingfromacknewconn")
                logger.debug(f"{event_type} from {gameevent_clid} {name} ")
                # if self.debug:
                #     if clid == self.playerone.client_id:
                #         logger.debug(f"{event_type} from {clid} {name} my connect ack!")
                #     else:
                #         logger.info(f"{event_type} from {clid} {name} - new player connected!")
            case "blkxplode":
                if self.debug:
                    logger.info(f"{event_type} from {game_event.get('fbomber')}")
            case "playerkilled" | "dmgkill":
                # if self.debug:
                dmgfrom = game_event.get("dmgfrom")
                dmgto = game_event.get("dmgto")
                self.client_game_state.players[dmgto]["score"] += 10
                kill_score = 1
                [
                    self.netplayers[k].set_texture(
                        arcade.load_texture("data/netplayerdead.png")
                    )
                    for k in self.netplayers
                    if k == dmgto
                ]  # [0]
                [
                    self.netplayers[k].addscore(kill_score)
                    for k in self.netplayers
                    if k == dmgfrom
                ]
                logger.info(f"{event_type} from {dmgfrom=}  {dmgto=}")
                # if dmgto == self.playerone.client_id:
                #     kill_score += self.playerone.kill(dmgfrom)
                #     logger.debug(f"{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} {kill_score=}")
                #     self._show_kill_screen = True
                #     self.show_kill_timer = game_event.get("killtimer")
                #     self.show_kill_timer_start = game_event.get("killstart")
                # if dmgfrom == self.playerone.client_id:
                #     self.playerone.score += kill_score
                #     logger.debug(f"{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} {kill_score=}")
                self.client_game_state.players[dmgto]["score"] += kill_score

            case "takedamage":
                pass
                # if self.debug:
                # dmgfrom = game_event.get("dmgfrom")
                # dmgto = game_event.get("dmgto")
                # damage = game_event.get("damage")
                # self.client_game_state.players[killed]['score'] += damage
                # [k.take_damage(damage, dmgfrom) for k in self.netplayers if k.client_id == killed]
                # logger.info(f'{event_type} from {dmgfrom=}  {killed=} {score=}')
                # if dmgto == self.playerone.client_id:
                #   self.playerone.score += damage
                #   self.playerone.take_damage(damage, dmgfrom)
                #    logger.debug(f"{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ")
                # self.client_game_state.players[killed]['score'] += score
            case "acktakedamage":
                pass
                # if self.debug:
                # dmgfrom = game_event.get("dmgfrom")
                # dmgto = game_event.get("dmgto")
                # damage = game_event.get("damage")
                # self.client_game_state.players[dmgfrom]['score'] += damage
                # self.client_game_state.players[dmgfrom]['health'] -= damage
                # if dmgto == self.playerone.client_id:
                #     self.playerone.take_damage(damage, dmgfrom)
                #     logger.debug(f"{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ")
                # elif dmgfrom == self.playerone.client_id:
                #     # self.playerone.score += damage
                #     logger.info(
                #         f"{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} "
                #     )

            case "ackbombxplode":
                bomber = game_event.get("bomber")
                # eventid = game_event.get("eventid")
                self.client_game_state.players[bomber]['bombsleft'] += 1
                # if bomber == self.playerone.client_id:
                #     if eventid == self.playerone.lastdrop:
                #         self.playerone.candrop = True
                #         self.playerone.bombsleft += 1
                #         logger.info(f"{game_event.get('event_type')} ownbombxfrom {bomber} p1={self.playerone}")
                # else:
                #     logger.info(f"{game_event.get('event_type')} otherbomb {bomber} p1={self.playerone}")
                #     pass
                # self.netplayers[bomber].bombsleft += 1
                # self.playerone.bombsleft += 1
                # self.client_game_state.players[bomber]['bombsleft'] += 1
                # self.netplayers[bomber].bombsleft += 1
                # pass #
            case "ackbullet":
                shooter = game_event.get("shooter")
                bullet_vel = Vec2d(
                    x=game_event.get("bullet_vel")[0],
                    y=game_event.get("bullet_vel")[1],
                )
                bulletpos = Vec2d(
                    x=game_event.get("pos")[0], y=game_event.get("pos")[1]
                )

                # position = Vec2d(x=self.center_x,y=self.center_y)-_bulletpos
                mnorm = bullet_vel.normalized()
                bulletpos += mnorm * 22

                # bulletpos_fix = get_map_coordinates_rev(bulletpos, self.guicamera)
                bullet = Bullet(
                    texture=self.bullet_sprite, scale=0.8, shooter=shooter
                )
                bullet.center_x = bulletpos.x
                bullet.center_y = bulletpos.y
                bullet.change_x = bullet_vel.x
                bullet.change_y = bullet_vel.y
                bullet.angle = game_event.get("ba")
                self.client_game_state.scene.add_sprite("Bullets", bullet)
            case "ackbombdrop":
                bomber = game_event.get("bomber")
                # eventid = game_event.get("eventid")
                bombpos = Vec2d(x=game_event.get("pos")[0], y=game_event.get("pos")[1])
                # bombpos_fix = get_map_coordinates_rev(bombpos, self.camera)
                bombtype = game_event.get("bombtype")
                if bombtype == 1:
                    bomb = Bomb("data/bomb.png", scale=0.5, bomber=bomber, timer=1500)
                else:
                    bomb = BiggerBomb("data/bomb.png", scale=0.7, bomber=bomber, timer=1500)
                bomb.center_x = bombpos.x
                bomb.center_y = bombpos.y
                self.client_game_state.scene.add_sprite("Bombs", bomb)
                # if (
                #     bomber == self.playerone.client_id
                #     and eventid == self.playerone.lastdrop
                # ):
                #     self.playerone.candrop = True  # player can drop again
                #     if self.debug:
                #         logger.info(f"{game_event.get('event_type')} ownbombfrom {bomber} pos {bombpos}  ")  # {eventid=} ld={self.playerone.lastdrop}
                # else:
                #     logger.debug(
                #         f"{game_event.get('event_type')} from {bomber} pos 	{bombpos} {bombpos_fix=}"
                #     )
            case _:
                # game_events.remove(game_event)
                logger.warning(f"unknown type:{event_type} {game_event=} ")

    def update_netplayers(self):
        pass
        # if self.playerone.client_id in self.client_game_state.players:
        #     try:
        #         playeronedata = self.client_game_state.players[self.playerone.client_id]
        #         self.playerone.update_netdata(playeronedata)
        #     except KeyError as e:
        #         logger.warning(f"keyerror {e} {self.client_game_state.players=} {self.playerone.client_id=}")

        for game_players in self.client_game_state.get_players():  # skip=self.playerone.client_id
            pclid = game_players.get("client_id")
            playerdata = game_players.get("playerdata")
            name = playerdata.get("name", "gsmissing")
            score = playerdata.get("score")
            angle = playerdata.get("angle")
            health = playerdata.get("health")
            bombsleft = playerdata.get("bombsleft")
            position = playerdata.get("position", (0, 0))
            value = f"  h:{health} s:{score} b:{bombsleft} pos: {position=} "
            if pclid in [k for k in self.netplayers if k != self.playerone.client_id]:  # update existing netplayer
                try:
                    self.netplayer_labels[pclid].value = value
                except KeyError as e:
                    logger.warning(f"KeyError {e} {pclid=} {self.netplayer_labels=} {value=}")
                for np in self.netplayers:
                    self.netplayers[np].position = position
                    self.netplayers[np].angle = angle
                    self.netplayers[np].name = name
                    self.netplayers[np].health = health
                    self.netplayers[np].score = score
                    self.netplayers[np].bombsleft = bombsleft
            else:  # create new netplayer
                position_fix = get_map_coordinates_rev(position, self.camera)
                if pclid == self.playerone.client_id:
                    # logger.warning(f'{gsplr=} {pclid=} {self.playerone.client_id=}')
                    newplayer = Bomberplayer(texture="data/playerone.png", client_id=pclid, name=name, position=position_fix, eventq=self.eventq)
                    playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), name=name, text_color=arcade.color.BLUE,)
                    playerlabel.button.text = f"Me {name}"
                else:
                    newplayer = Bomberplayer(texture="data/netplayer.png", client_id=pclid, name=name, position=position_fix, eventq=self.eventq)
                    playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), name=name, text_color=arcade.color.GREEN,)
                    playerlabel.button.text = f"{name}"
                    logger.info(f"newplayer: {name} id={newplayer.client_id} pos: {position} fix={position_fix} ")
                if pclid != self.playerone.client_id:
                    self.client_game_state.scene.add_sprite("Netplayers", newplayer)
                    self.netplayers[pclid] = (newplayer)  # {'client_id':pclid, 'position':position_fix}
                    self.netplayer_labels[pclid] = playerlabel
                    self.netplayer_grid.add(playerlabel.button, col_num=0, row_num=len(self.netplayer_labels),)
                    self.netplayer_grid.add(playerlabel.textlabel, col_num=1, col_span=2, row_num=len(self.netplayer_labels),)  # h
                # if pclid != self.playerone.client_id:

    def update_poplist(self):
        for p in self.poplist:
            logger.info(f"plist={self.poplist} popping {p} gsp={self.client_game_state.players}")
            self.client_game_state.players.pop(p)
            logger.info(f"aftergsp={self.client_game_state.players}")
        self.poplist = []

def on_update(self, dt):
    self.timer += dt
    if not self._gotmap:
        if self.debug:
            logger.warning(f"{self} no map!")
        return

    try:
        self.handle_game_events(self.client_game_state.event_queue.get_nowait())
        # game_events = self.client_game_state.event_queue.get_nowait()
        self.client_game_state.event_queue.task_done()
    except Empty:
        pass

    self.update_netplayers()
    self.update_poplist()
    for b in self.client_game_state.scene["Bullets"]:
        b.update()
    self.center_camera_on_player()  # Center the camera on the player
    self.player_list.update()
