"""有图形显示时执行真实 Tk 控件冒烟测试；无显示环境明确跳过。"""
import gc
import os
from pathlib import Path
import subprocess
import sys
import unittest

# Direct execution in the child must find the application modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from engine import Game, make_deck
from main import App
from network import Client


class GuiSmokeTests(unittest.TestCase):
    def test_build_lobby_table_cards_and_dialog(self):
        if os.environ.get('UNO_GUI_TEST_CHILD') != '1':
            # A destroyed Tk window can leave Python reference cycles behind.
            # Keep those objects out of the process running TCP worker threads.
            env = os.environ.copy()
            env['UNO_GUI_TEST_CHILD'] = '1'
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), '-v'],
                env=env, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=60,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0,
                             f'GUI subprocess failed:\n{output}')
            if 'GUI_DISPLAY_UNAVAILABLE:' in output:
                self.skipTest('No graphical display is available in the GUI subprocess.')
            return
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'GUI_DISPLAY_UNAVAILABLE: {exc}')
        app = None
        try:
            app = App(root)
            root.update()
            app.client = Client()
            app.client.connected = True
            app._table_shell()
            g = Game(['测试玩家', '测试对手'], seed=2)
            # 界面测试专用手牌，展示每一种功能牌；不用于规则守恒测试。
            seen = set()
            g.players[0].hand = []
            for c in make_deck():
                if c.kind not in seen:
                    seen.add(c.kind)
                    g.players[0].hand.append(c)
            app.state = {'seat': 0, 'host': True, 'paused': False,
                         'members': [{'name': p.name, 'bot': False, 'connected': True, 'total': 0}
                                     for p in g.players], 'game': g.view(0)}
            app.render()
            root.update()
            self.assertTrue(app.hand_canvas.find_all())
            self.assertTrue(app.table.find_all())
            if g.legal(0):
                app.select(g.legal(0)[0])
                self.assertEqual(app.selected,g.legal(0)[0])
            app.choose('测试选择', [('红', 'red')], lambda _: None)
            root.update()
            self.assertTrue(app.dialog.winfo_exists())
            app.dialog.destroy()
            app.help()
            root.update()
        finally:
            if app and app.client:
                app.client.close()
            # Stop pending callbacks and collect GUI cycles on this main thread.
            for callback in root.tk.splitlist(root.tk.call('after', 'info')):
                root.after_cancel(callback)
            root.destroy()
            app = None
            root = None
            gc.collect()


if __name__ == '__main__':
    unittest.main()
