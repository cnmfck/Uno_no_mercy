"""作者模式权限、自由出牌、造牌守恒增量与中央抽牌入口。"""
import unittest
from types import SimpleNamespace
from engine import Game, Card, RuleError
from effects import seat_color
from main import App


class V6Tests(unittest.TestCase):
    def test_admin_any_turn_any_card_repeated(self):
        g=Game(['admin','普通','朋友'],seed=1)
        g.current=1
        g.color='red'
        g.discard=[Card(999,'red','5')]
        g.players[0].hand=[Card(1000,'blue','1'),Card(1001,'green','2'),Card(1002,'blue','3')]
        g.pending,g.last_draw=10,10
        g.act(0,{'op':'play','card':1000})
        self.assertEqual(g.pending,0)
        self.assertEqual(g.current,1)
        g.act(0,{'op':'play','card':1001})
        self.assertEqual(len(g.players[0].hand),1)
        self.assertTrue(g.recent[-1]['gold'])

    def test_forge_all_black_types_unique(self):
        g=Game(['op','普通'],seed=1)
        for kind in ('reverse4','draw6','draw10','roulette'):
            g.act(0,{'op':'forge','kind':kind})
            self.assertEqual(g.players[0].hand[-1].kind,kind)
        self.assertEqual(len(g.players[0].hand),11)
        self.assertEqual(len({c.uid for c in g.players[0].hand}),11)
        self.assertEqual(seat_color({'game':g.view(0)},0),'#ffda69')

    def test_normal_cannot_forge_or_ignore_turn(self):
        g=Game(['普通','朋友'],seed=1)
        for action in ({'op':'forge','kind':'draw10'},{'op':'play','card':g.players[1].hand[0].uid}):
            before=g.view(1)
            with self.assertRaises(RuleError):g.act(1,action)
            self.assertEqual(before,g.view(1))

    def test_forge_rejects_invalid_and_out(self):
        g=Game(['admin','朋友'],seed=1)
        with self.assertRaises(RuleError):g.act(0,{'op':'forge','kind':'draw2'})
        g.players[0].out=True
        self.assertEqual(g.legal(0),[])
        with self.assertRaises(RuleError):g.act(0,{'op':'forge','kind':'draw10'})

    def test_central_penalty_only_without_stack(self):
        calls=[]
        game={'current':0,'winner':None,'legal':[],'pending':12,'players':[{'out':False}]}
        app=SimpleNamespace(state={'seat':0,'game':game,'paused':False},
            table=SimpleNamespace(winfo_width=lambda:1000,winfo_height=lambda:300),send=lambda op:calls.append(op))
        App._table_click(app,SimpleNamespace(x=500,y=150))
        self.assertEqual(calls,['draw'])
        game['legal']=[12]
        App._table_click(app,SimpleNamespace(x=500,y=150))
        self.assertEqual(calls,['draw'])

    def test_ordinary_draw_from_deck(self):
        calls=[]
        game={'current':0,'winner':None,'legal':[],'pending':0,'players':[{'out':False}]}
        app=SimpleNamespace(state={'seat':0,'game':game,'paused':False},
            table=SimpleNamespace(winfo_width=lambda:1000,winfo_height=lambda:300),send=lambda op:calls.append(op))
        App._table_click(app,SimpleNamespace(x=500,y=150))
        App._table_click(app,SimpleNamespace(x=840,y=135))
        self.assertEqual(calls,['draw'])
