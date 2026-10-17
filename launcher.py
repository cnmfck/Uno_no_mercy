"""Packaged application entry point and build verification commands."""
import argparse
import json
from pathlib import Path
import platform
import sys
import traceback

import main


def verify(graphical):
    import tkinter as tk
    from engine import Game, make_deck
    from network import PROTOCOL

    assert len(make_deck()) == 168
    game = Game(['Build check', 'Bot'], bots=[1], seed=1)
    assert len(game.players[0].hand) == 7
    interp = tk.Tcl()
    if graphical:
        root = tk.Tk()
        app = None
        try:
            app = main.App(root)
            root.update()
        finally:
            if app:
                app.close()
            else:
                root.destroy()
    return {
        'status': 'passed', 'graphical': graphical,
        'platform': platform.platform(), 'architecture': platform.machine(),
        'python': platform.python_version(), 'protocol': PROTOCOL,
        'tcl': interp.eval('info patchlevel'),
        'frozen': bool(getattr(sys, 'frozen', False)),
    }


def run():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not (args.self_check or args.smoke_test):
        main.main()
        return 0
    try:
        result = verify(args.smoke_test)
        status = 0
    except Exception:
        result = {'status': 'failed', 'traceback': traceback.format_exc()}
        status = 1
    output = json.dumps(result, indent=2)
    if args.report:
        args.report.write_text(output + '\n', encoding='utf-8')
    if sys.stdout:
        print(output)
    return status


if __name__ == '__main__':
    raise SystemExit(run())
