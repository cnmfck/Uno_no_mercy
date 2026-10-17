"""选色轮盘方向、权威等待以及公开抽牌事件回归检查。"""
import unittest
import time
import threading
from types import SimpleNamespace
from engine import Game, Card, RuleError
from network import Room
from color_wheel import sector


class V5Tests(unittest.TestCase):
    def test_wheel_directions_and_dead_zone(self):
        for point,color in [((230,80),'red'),((380,230),'blue'),((230,380),'green'),((80,230),'yellow')]:
            self.assertEqual(sector(*point),color)
        self.assertIsNone(sector(230,230))
        self.assertIsNone(sector(0,0))

    def test_roulette_events_public_and_ordered(self):
        g=Game(['甲','乙','丙'],seed=1)
        g.players[0].hand.insert(0,Card(1000,'wild','roulette'))
        g.deck=[Card(1003,'red','2'),Card(1002,'blue','3')]
        g.act(0,dict(op='play',card=1000,color='red'))
        events=g.view(2)['effects']
        color,reveal=events[-2:]
        self.assertEqual((color['kind'],color['seat'],color['color']),('color',0,'red'))
        self.assertEqual((reveal['kind'],reveal['seat'],reveal['count']),('reveal',1,2))
        self.assertEqual([c['color'] for c in reveal['cards']],['blue','red'])
        self.assertGreater(g.visual_until-time.monotonic(),1.9)
        self.assertEqual(g.current,2)

    def test_server_blocks_actions_during_result(self):
        room=Room.__new__(Room)
        room.lock=threading.RLock()
        room.seats=[{'owner':False}]
        room.game=Game(['甲','乙'])
        room.game.visual_until=time.monotonic()+1
        room.paused=lambda:False
        with self.assertRaisesRegex(RuleError,'正在展示'):
            room.handle_action(SimpleNamespace(seat=0),{'op':'draw','revision':0})

    def test_missing_color_does_not_mutate(self):
        g=Game(['甲','乙'])
        g.players[0].hand.insert(0,Card(1000,'wild','roulette'))
        before=g.view(0)
        with self.assertRaises(RuleError):
            g.act(0,{'op':'play','card':1000})
        self.assertEqual(g.view(0),before)
