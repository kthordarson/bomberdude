#!/usr/bin/python
from arcade.gui import UIGridLayout
from arcade.gui.widgets.layout import UIAnchorLayout

def debug_dump_game(game):
    bar = f"{'=' * 20}"
    shortbar = f"{'=' * 5}"
    print(f"{bar} {game.playerone.client_id} {bar}")
    print(f"bombs:{len(game.bomb_list)} particles:{len(game.particle_list)} flames:{len(game.flame_list)}")
    print(f"playerone: {game.playerone} pos={game.playerone.position} ")
    # gspos={game.game_state.players[game.playerone.client_id]}')
    print(f"game.game_state.players = {len(game.game_state.players)} netplayers = {len(game.netplayers)}")
    print(f"{shortbar} {game.game_state} {shortbar}")
    print(f"gsp = {game.game_state.players}")
    print(f"{bar} netplayers {bar}")
    print(f"netplayers = {game.netplayers}")
    print(f"{bar} gamestateplayers {bar}")
    for idx, p in enumerate(game.game_state.players):
        gsp = game.game_state.players.get(p)
        print(
            f"\t{idx}/{len(game.game_state.players)} p={p} | name:{gsp['name']} {gsp['client_id']} {gsp['position']} a={gsp['angle']} h={gsp['health']} s={gsp['score']} to={gsp['timeout']} to={gsp['killed']}"
        )
    print(f"{bar} netplayers {bar}")
    for idx, p in enumerate(game.netplayers):
        np = game.netplayers.get(p)
        print(
            f"\t{idx}/{len(game.game_state.players)} p={p} | name: {np.name} {np.client_id} {np.position} a={np.angle} h={np.health} s={np.score} to={np.timeout} to={np.killed}"
        )
    # print('='*80)
    # arcade.print_timings()
    # print('='*80)


def debug_dump_widgets(game):
    print("=" * 80)
    for k in game.manager.walk_widgets():
        print(f"widgetwalk {k=}")
        if isinstance(k, UIGridLayout):
            for sub in k.children:
                print(f"\tUIG  {sub=}")
        elif isinstance(k, UIAnchorLayout):
            for sub in k.children:
                print(f"\tUIA  {sub=}")
                for xsub in sub.children:
                    print(f"\t   UIA   {xsub=}")
        else:
            print(f"\t {k=} {type(k)}")
    print("=" * 80)
    for item in game.manager.walk_widgets():
        print(f"{item=} {item.position} {item.x} {item.y}")
        for sub in item.children:
            print(f"\tsubitem  {sub} {sub.position} {sub.x} {sub.y}")
            for subsub in sub.children:
                print(
                    f"\t - SUBsubitem   {subsub} {subsub.position} {subsub.x} {subsub.y}"
                )
    print("=" * 80)
