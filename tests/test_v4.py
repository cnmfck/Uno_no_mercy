"""事件只带公开数据；特效不能干扰回合，重连不能重播历史动画。"""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from engine import Game, Card
from effects import Effects, PLAYER_COLORS
from main import App
from network import Room
import threading


class V4Tests(unittest.TestCase):
    def game(self):
        g = Game(['甲','乙','丙'],seed=1)
        g.discard = [Card(1000,'red','5')]
        g.color = 'red'
        return g

    def test_shout_anytime_without_changing_turn(self):
        g = self.game()
        before = (g.current,g.revision,len(g.players[1].hand))
        g.act(1,{'op':'shout'})
        self.assertEqual(before,(g.current,g.revision,len(g.players[1].hand)))
        g.players[1].out = True
        g.winner = 0
        g.act(1,{'op':'shout'})
        self.assertEqual(g.effects[-1]['kind'],'uno')

    def test_shout_declares_single(self):
        g = self.game()
        g.players[1].hand = [Card(1001,'blue','3')]
        g.uno_open = {1}
        g.act(1,{'op':'shout'})
        self.assertNotIn(1,g.uno_open)

    def test_penalty_events_count_and_privacy(self):
        g = self.game()
        g.pending,g.last_draw = 10,10
        g.act(0,{'op':'draw'})
        event = g.view(1)['effects'][-1]
        self.assertEqual((event['kind'],event['seat'],event['count']),('draw',0,10))
        self.assertFalse({'card','cards','hand'} & event.keys())

    def test_swap_and_pass_endpoints(self):
        for kind in ('7','0'):
            g = self.game()
            g.players[0].hand.insert(0,Card(1001,'red',kind))
            counts = [len(p.hand) for p in g.players]
            counts[0] -= 1
            g.act(0,{'op':'play','card':1001,'target':1})
            event = next(e for e in reversed(g.effects) if e['kind'] in ('swap','pass'))
            for origin,dest,count in event['moves']:
                self.assertEqual(count,counts[origin])
                self.assertEqual(count,len(g.players[dest].hand))

    def test_dedup_and_reconnect(self):
        with patch('effects.sys.platform','linux'):
            fx = Effects(SimpleNamespace(root=None))
        g = self.game()
        fx.consume(g.view(0))
        self.assertEqual(len(fx.active),3)
        fx.consume(g.view(0))
        self.assertEqual(len(fx.active),3)
        g.act(2,{'op':'shout'})
        fx.consume(g.view(0))
        self.assertEqual(len(fx.active),4)
        g.revision = 2
        fx.round = None
        fx.consume(g.view(0))
        self.assertEqual(fx.active,[])

    def test_avatar_drop_excludes_self_and_retired(self):
        widgets = {i:SimpleNamespace(winfo_rootx=lambda i=i:i*100,winfo_rooty=lambda:0,
                                    winfo_width=lambda:80,winfo_height=lambda:76) for i in range(3)}
        app = SimpleNamespace(state={'seat':0,'game':{'players':[{'out':False},{'out':False},{'out':True}]}},avatar_widgets=widgets)
        self.assertIsNone(App._avatar_target(app,40,30))
        self.assertEqual(App._avatar_target(app,140,30),1)
        self.assertIsNone(App._avatar_target(app,240,30))
        self.assertEqual(len(set(PLAYER_COLORS)),6)

    def test_network_shout_preserves_bot_deadline(self):
        room = Room.__new__(Room)
        room.lock = threading.RLock()
        room.seats = [{'owner':False}]
        room.game = self.game()
        room.next_bot = 123.5
        sent = []
        room.broadcast = lambda: sent.append(True)
        room.handle_action(SimpleNamespace(seat=0),{'op':'shout','revision':-999})
        self.assertEqual(room.next_bot,123.5)
        self.assertEqual(sent,[True])


if __name__ == '__main__':
    unittest.main()
