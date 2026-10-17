"""抽一张规则及新交互边界，避免普通抽牌、叠加惩罚和轮盘互相影响。"""
import unittest
from types import SimpleNamespace
from engine import Game, Card, RuleError
from card_art import pile_hit
from main import App


class V3Tests(unittest.TestCase):
    def setup_game(self, drawn):
        g=Game(['甲','乙','丙'],seed=9)
        g.discard=[Card(800,'red','5')]
        g.color='red'
        g.players[0].hand=[Card(801,'blue','1')]
        g.deck=[Card(802,'green','8'),drawn]
        return g

    def test_unplayable_draws_exactly_one_and_passes(self):
        g=self.setup_game(Card(803,'green','3'))
        g.act(0,{'op':'draw'})
        self.assertEqual(len(g.deck),1)
        self.assertEqual(len(g.players[0].hand),2)
        self.assertEqual(g.current,1)
        self.assertIsNone(g.forced)

    def test_matching_color_number_symbol_and_wild(self):
        for color,kind in [('red','9'),('green','5'),('wild','draw6')]:
            with self.subTest(color=color,kind=kind):
                g=self.setup_game(Card(803,color,kind))
                g.act(0,{'op':'draw'})
                self.assertEqual(g.forced,803)
                self.assertEqual(g.current,0)
                self.assertEqual(g.legal(0),[803])
                with self.assertRaises(RuleError):
                    g.act(0,{'op':'draw'})
                g.act(0,{'op':'play','card':803,'color':'blue'})
                self.assertIsNone(g.forced)

    def test_drawn_seven_requires_target(self):
        g=self.setup_game(Card(803,'red','7'))
        g.act(0,{'op':'draw'})
        with self.assertRaises(RuleError):
            g.act(0,{'op':'play','card':803})
        g.act(0,{'op':'play','card':803,'target':1})
        self.assertEqual(g.current,1)

    def test_penalty_still_multiple_cards(self):
        g=self.setup_game(Card(803,'red','9'))
        g.deck=[Card(900+i,'green','2') for i in range(20)]
        g.pending,g.last_draw=10,10
        g.act(0,{'op':'draw'})
        self.assertEqual(len(g.players[0].hand),11)
        self.assertEqual(g.current,1)

    def test_draw_event_does_not_leak_other_hand(self):
        g=self.setup_game(Card(803,'red','9'))
        g.act(0,{'op':'draw'})
        self.assertEqual(g.view(0)['draw_event']['card']['uid'],803)
        self.assertIsNone(g.view(1)['draw_event']['card'])
        self.assertIsNone(g.view(2)['draw_event']['card'])

    def test_center_drop_target_resizes(self):
        for w,h in [(600,220),(1100,320),(1700,500)]:
            self.assertTrue(pile_hit(w/2,h*.51,w,h))
            self.assertFalse(pile_hit(w*.15,h*.51,w,h))
            self.assertFalse(pile_hit(w*.84,h*.45,w,h))

    def test_stale_auto_callback_cannot_play(self):
        calls=[]
        g=self.setup_game(Card(803,'red','9'))
        g.act(0,{'op':'draw'})
        app=SimpleNamespace(state={'game':g.view(0),'seat':0,'paused':False},
                            client=SimpleNamespace(connected=True),
                            select=lambda uid:calls.append(uid),play=lambda:calls.append('play'))
        App._auto_play_drawn(app,('old-round',803))
        self.assertEqual(calls,[])
        App._auto_play_drawn(app,(g.round_id,803))
        self.assertEqual(calls,[803,'play'])

    def test_paused_auto_callback_cannot_play(self):
        g=self.setup_game(Card(803,'red','9'))
        g.act(0,{'op':'draw'})
        app=SimpleNamespace(state={'game':g.view(0),'seat':0,'paused':True})
        App._auto_play_drawn(app,(g.round_id,803))


if __name__=='__main__':
    unittest.main()
