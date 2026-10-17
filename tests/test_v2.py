"""第二版边界：清牌退场、36 张死亡、终局人数、公开历史与动画输入。"""
import unittest
import time
from types import SimpleNamespace
from engine import Game, Card, RuleError, DRAW
from network import BOT_DELAY
from visuals import draw_scene, draw_podium


class V2Tests(unittest.TestCase):
    def game(self, n=4, remaining=1):
        return Game([str(i) for i in range(n)], seed=4, end_remaining=remaining)

    def test_35_alive_36_dead(self):
        g = self.game()
        g.players[0].hand = [Card(1000+i,'red','2') for i in range(34)]
        g._take(0)
        self.assertFalse(g.players[0].out)
        g._take(0)
        self.assertTrue(g.players[0].out)
        self.assertEqual(g.players[0].death_count,36)

    def test_multiple_finishers(self):
        g=self.game()
        for i in (2,0):
            g.players[i].hand=[]
            g._win(i)
            self.assertIsNone(g.winner)
        g.players[3].hand=[]
        g._win(3)
        self.assertEqual([x['seat'] for x in g.ranking],[2,0,3,1])
        self.assertEqual(g.finish_order,[2,0,3])

    def test_end_remaining_and_death_last(self):
        g=self.game(5,2)
        g.players[0].hand=[]
        g._win(0)
        g.players[1].hand=[Card(1000+i,'red','2') for i in range(35)]
        g._take(1)
        self.assertIsNone(g.winner)
        g.players[4].hand=[]
        g._win(4)
        self.assertEqual([x['seat'] for x in g.ranking][:2],[0,4])
        self.assertEqual(g.ranking[-1]['seat'],1)
        self.assertEqual(g.ranking[-1]['count'],36)
        self.assertEqual(g.ranking[2]['rank'],g.ranking[3]['rank'])

    def test_invalid_settings(self):
        for value in (0,4,True,'1',-1):
            with self.assertRaises(RuleError):
                self.game(4,value)

    def test_finish_last_draw_effect_continues(self):
        g=self.game()
        c=Card(1000,'wild','draw6')
        g.players[0].hand=[c]
        g.act(0,dict(op='play',card=1000,color='red'))
        self.assertEqual(g.finish_order,[0])
        self.assertEqual(g.pending,6)
        self.assertEqual(g.current,1)
        self.assertEqual(g.draw_chain,[c.public()])

    def test_recent_limited_and_chain(self):
        g=self.game()
        for i in range(7):
            seat=g.current
            c=Card(1000+i,'red','draw2')
            g.players[seat].hand.append(c)
            g.color='red'
            g.act(seat,dict(op='play',card=c.uid))
        self.assertEqual(len(g.recent),5)
        self.assertEqual(len(g.draw_chain),7)
        self.assertEqual(g.pending,14)
        g.act(g.current,dict(op='draw'))
        self.assertEqual(g.draw_chain,[])

    def test_finished_seat_skipped(self):
        g=self.game()
        g.players[1].hand=[]
        g._win(1)
        self.assertEqual(g.next_seat(0),2)
        self.assertEqual(g.legal(1),[])

    def test_empty_deck_can_stop_safely(self):
        g=self.game()
        g.deck=[]
        g.discard=g.discard[-1:]
        self.assertIsNone(g._take(0))

    def test_bot_delay(self):
        self.assertEqual(BOT_DELAY,1.5)

    def test_many_settings_full_games(self):
        for n in range(2,7):
            for remaining in range(1,n):
                for seed in range(12):
                    g=Game([str(i) for i in range(n)],seed=seed,end_remaining=remaining)
                    for _ in range(4000):
                        cards=g.deck+g.discard+g.retired+[c for p in g.players for c in p.hand]
                        self.assertEqual(len(cards),168)
                        self.assertEqual(len({c.uid for c in cards}),168)
                        if g.winner is not None:
                            break
                        self.assertIn(g.current,g.active())
                        g.act(g.current,g.bot_action(g.current))
                    self.assertIsNotNone(g.winner)
                    self.assertEqual(len(g.ranking),n)
                    self.assertLessEqual(len(g.active()),remaining)

    def test_visual_commands_without_display(self):
        # 校验所有绘制分支与数值，不能替代真实桌面外观检查。
        class Canvas:
            def __init__(self): self.items=[]
            def winfo_width(self): return 650
            def winfo_height(self): return 220
            def delete(self,*a): self.items=[]
            def __getattr__(self,name):
                if name.startswith('create_'):
                    return lambda *a,**kw:self.items.append((name,a,kw))
                raise AttributeError(name)
        g=self.game()
        g.draw_chain=[Card(2000+i,'wild' if k not in ('draw2','draw4') else 'red',k).public()
                      for i,k in enumerate(list(DRAW)*3)]
        g.pending=sum(DRAW[c['kind']] for c in g.draw_chain)
        canvas=Canvas()
        app=SimpleNamespace(table=canvas,state={'game':g.view(0)},effect_since=time.monotonic(),
                            death_since=time.monotonic(),death_names=['测试玩家'])
        draw_scene(app)
        self.assertTrue(canvas.items)
        g.end_remaining=3
        g.players[0].hand=[]
        g._win(0)
        draw_podium(canvas,g.view(0))
        self.assertTrue(canvas.items)


if __name__=='__main__':
    unittest.main()
