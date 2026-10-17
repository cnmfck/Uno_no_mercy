"""运行 python -m unittest discover -s tests -v。

定向用例为特殊牌构造短小牌桌；随机完整对局检查唯一牌守恒及流程终止。
"""
import unittest
from collections import Counter
from engine import Game, Card, make_deck, RuleError, COLORS, DRAW


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.g = Game(['甲', '乙', '丙'], seed=7)
        self.uid = 1000
        self.g.discard = [self.c('red', '5')]
        self.g.color = 'red'
        for p in self.g.players:
            p.hand = [self.c('blue', '1'), self.c('green', '2')]

    def c(self, color, kind):
        self.uid += 1
        return Card(self.uid, color, kind)

    def play(self, kind, color='red', seat=0, **extra):
        c = self.c(color, kind)
        self.g.players[seat].hand.insert(0, c)
        self.g.act(seat, dict(op='play', card=c.uid, **extra))
        return c

    def test_deck_composition(self):
        cards = make_deck()
        self.assertEqual(len(cards), 168)
        self.assertEqual(len({c.uid for c in cards}), 168)
        self.assertEqual(Counter(c.color for c in cards), dict(red=36, yellow=36, green=36, blue=36, wild=24))
        counts = Counter(c.kind for c in cards)
        self.assertEqual(counts['draw2'], 12)
        self.assertEqual(counts['reverse4'], 8)
        self.assertEqual(counts['roulette'], 8)

    def test_setup(self):
        g = Game(['甲', '乙'], seed=0)
        self.assertEqual([len(p.hand) for p in g.players], [7, 7])
        self.assertTrue(g.discard[-1].kind.isdigit())

    def test_color_number_symbol_matching(self):
        for color, kind in [('red', '1'), ('blue', '5'), ('wild', 'draw6')]:
            self.assertTrue(self.g.matches(self.c(color, kind)))
        self.assertFalse(self.g.matches(self.c('blue', '2')))
        self.g.discard = [self.c('red', 'skip')]
        self.assertTrue(self.g.matches(self.c('blue', 'skip')))

    def test_invalid_play_is_atomic(self):
        self.g.uno_open = {1}
        before = self.g.view(0)
        with self.assertRaises(RuleError):
            self.g.act(0, {'op': 'play', 'card': self.g.players[0].hand[0].uid})
        self.assertEqual(before, self.g.view(0))

    def test_wrong_turn(self):
        with self.assertRaises(RuleError):
            self.g.act(1, {'op': 'draw'})

    def test_seven_swap(self):
        before0 = list(self.g.players[0].hand)
        before1 = list(self.g.players[1].hand)
        self.play('7', target=1)
        self.assertEqual(self.g.players[0].hand, before1)
        self.assertEqual(self.g.players[1].hand, before0)
        self.assertEqual(self.g.current, 1)

    def test_invalid_swap_target_atomic(self):
        c = self.c('red', '7')
        self.g.players[0].hand.append(c)
        before = self.g.view(0)
        for target in [0, 9, '1', None]:
            with self.assertRaises(RuleError):
                self.g.act(0, dict(op='play', card=c.uid, target=target))
            self.assertEqual(before, self.g.view(0))

    def test_zero_pass(self):
        old = [p.hand[:] for p in self.g.players]
        self.play('0')
        self.assertEqual([p.hand for p in self.g.players], [old[2], old[0], old[1]])

    def test_zero_reverse_pass(self):
        self.g.direction = -1
        old = [p.hand[:] for p in self.g.players]
        self.play('0')
        self.assertEqual([p.hand for p in self.g.players], [old[1], old[2], old[0]])

    def test_zero_ignores_eliminated(self):
        self.g.players[1].out = True
        old0, old2 = self.g.players[0].hand[:], self.g.players[2].hand[:]
        self.play('0')
        self.assertEqual(self.g.players[0].hand, old2)
        self.assertEqual(self.g.players[2].hand, old0)

    def test_skip(self):
        self.play('skip')
        self.assertEqual(self.g.current, 2)

    def test_reverse(self):
        self.play('reverse')
        self.assertEqual(self.g.direction, -1)
        self.assertEqual(self.g.current, 2)

    def test_two_player_reverse(self):
        self.g.players.pop()
        self.play('reverse')
        self.assertEqual(self.g.current, 0)

    def test_two_player_skip(self):
        self.g.players.pop()
        self.play('skip')
        self.assertEqual(self.g.current, 0)

    def test_skip_everyone(self):
        self.play('skip_all')
        self.assertEqual(self.g.current, 0)

    def test_discard_all_keeps_action_on_top(self):
        self.g.players[0].hand += [self.c('red', '7'), self.c('red', 'draw4')]
        c = self.play('discard')
        self.assertEqual(self.g.discard[-1], c)
        self.assertEqual(len(self.g.players[0].hand), 2)
        self.assertEqual(self.g.pending, 0)
        self.assertEqual(self.g.current, 1)

    def test_all_draw_types(self):
        for kind, value in DRAW.items():
            with self.subTest(kind=kind):
                self.setUp()
                wild = kind in ('reverse4', 'draw6', 'draw10')
                c = self.c('wild' if wild else 'red', kind)
                self.g.players[0].hand.append(c)
                self.g.act(0, {'op': 'play', 'card': c.uid, 'color': 'blue'})
                self.assertEqual(self.g.pending, value)
                self.assertEqual(self.g.last_draw, value)
                self.assertEqual(self.g.current, 2 if kind == 'reverse4' else 1)
                target = self.g.current
                self.g.act(target, {'op': 'draw'})
                self.assertEqual(len(self.g.players[target].hand), 2+value)
                self.assertEqual(self.g.pending, 0)
                self.assertNotEqual(self.g.current, target)

    def test_stack_compares_last_not_total(self):
        self.play('draw4')
        for seat in (1, 2):
            c = self.c('wild', 'draw6')
            self.g.players[seat].hand.append(c)
            self.g.act(seat, dict(op='play', card=c.uid, color='blue'))
        self.assertEqual(self.g.pending, 16)
        self.assertEqual(self.g.last_draw, 6)

    def test_cross_color_stack(self):
        self.play('draw2')
        self.play('draw4', 'blue', 1)
        self.assertEqual(self.g.pending, 6)

    def test_smaller_stack_rejected(self):
        self.play('draw4')
        c = self.c('red', 'draw2')
        self.g.players[1].hand.append(c)
        self.assertNotIn(c.uid, self.g.legal(1))

    def test_two_player_reverse4_and_stack_back(self):
        self.g.players.pop()
        c = self.c('wild', 'reverse4')
        self.g.players[0].hand.append(c)
        self.g.act(0, dict(op='play', card=c.uid, color='green'))
        self.assertEqual(self.g.current, 0)
        self.assertEqual(self.g.pending, 4)
        c = self.c('wild', 'draw6')
        self.g.players[0].hand.append(c)
        self.g.act(0, dict(op='play', card=c.uid, color='blue'))
        self.assertEqual(self.g.current, 1)
        self.assertEqual(self.g.pending, 10)

    def test_wild_requires_color_without_mutation(self):
        c = self.c('wild', 'draw10')
        self.g.players[0].hand.append(c)
        before = self.g.view(0)
        with self.assertRaises(RuleError):
            self.g.act(0, dict(op='play', card=c.uid))
        self.assertEqual(before, self.g.view(0))

    def test_roulette_playing_player_chooses_and_reveals(self):
        draw = [self.c('blue', '2'), self.c('wild', 'draw6'), self.c('red', '3')]
        self.g.deck = list(reversed(draw))
        c=self.c('wild','roulette')
        self.g.players[0].hand.insert(0,c)
        self.g.act(0,dict(op='play',card=c.uid,color='red'))
        self.assertEqual(len(self.g.players[1].hand), 5)
        self.assertEqual([c['uid'] for c in self.g.revealed], [c.uid for c in draw])
        self.assertEqual(self.g.current, 2)
        self.assertEqual(self.g.color, 'red')
        self.assertFalse(self.g.roulette)

    def test_roulette_rejects_draw(self):
        with self.assertRaises(RuleError):
            self.play('roulette','wild')

    def test_draw_one_playable_is_forced(self):
        matching = self.c('red', '9')
        self.g.deck = [self.c('green', '3'), self.c('blue', '2'), matching]
        self.g.act(0, {'op': 'draw'})
        self.assertEqual(len(self.g.players[0].hand), 3)
        self.assertEqual(self.g.legal(0), [matching.uid])
        with self.assertRaises(RuleError):
            self.g.act(0, {'op': 'draw'})
        self.g.act(0, dict(op='play', card=matching.uid))
        self.assertEqual(self.g.current, 1)

    def test_cannot_draw_with_matching_card(self):
        self.g.players[0].hand.append(self.c('red', '3'))
        with self.assertRaises(RuleError):
            self.g.act(0, {'op': 'draw'})

    def test_death_at_36(self):
        self.g.players[0].hand = [self.c('blue', '2') for _ in range(35)]
        self.g.deck = [self.c('red', '1')]
        self.g.act(0, {'op': 'draw'})
        self.assertTrue(self.g.players[0].out)
        self.assertEqual(len(self.g.retired), 36)
        self.assertEqual(self.g.current, 1)

    def test_penalty_stops_at_elimination(self):
        self.g.players[0].hand = [self.c('blue', '2') for _ in range(35)]
        self.g.pending, self.g.last_draw = 20, 10
        before = len(self.g.deck)
        self.g.act(0, {'op': 'draw'})
        self.assertEqual(len(self.g.deck), before-1)
        self.assertEqual(self.g.pending, 0)

    def test_roulette_elimination(self):
        self.g.players[1].hand = [self.c('blue', '2') for _ in range(35)]
        c=self.c('wild','roulette')
        self.g.players[0].hand.insert(0,c)
        self.g.act(0,dict(op='play',card=c.uid,color='red'))
        self.assertTrue(self.g.players[1].out)
        self.assertEqual(len(self.g.revealed), 1)
        self.assertEqual(self.g.current, 2)

    def test_last_survivor_wins(self):
        self.g.players.pop()
        self.g.players[0].hand = [self.c('blue', '2') for _ in range(35)]
        self.g.deck = [self.c('blue', '1')]
        self.g.act(0, {'op': 'draw'})
        self.assertEqual(self.g.winner, 1)
        self.assertEqual(self.g.score, 250)

    def test_reshuffle_preserves_top_and_retired(self):
        top = self.g.discard[-1]
        self.g.deck = []
        retired = self.c('blue', '4')
        self.g.retired = [retired]
        self.assertEqual(self.g._take(0), retired)
        self.assertEqual(self.g.discard, [top])
        self.assertEqual(self.g.retired, [])

    def test_final_seven_and_zero_win_immediately(self):
        for kind in ('7', '0', 'draw2', 'discard', 'skip_all'):
            self.setUp()
            c = self.c('red', kind)
            self.g.players[0].hand = [c]
            self.g.act(0, dict(op='play', card=c.uid))
            self.assertEqual(self.g.finish_order, [0])
            self.assertIsNone(self.g.winner)
            self.assertNotEqual(self.g.current, 0)

    def test_discard_all_win(self):
        self.g.players[0].hand = [self.c('red', '2'), self.c('red', 'skip')]
        self.play('discard')
        self.assertEqual(self.g.finish_order, [0])

    def test_uno_catch_and_declare(self):
        self.g.players[0].hand = [self.c('blue', '1')]
        self.play('2')
        self.assertIn(0, self.g.uno_open)
        self.g.act(1, dict(op='catch', target=0))
        self.assertEqual(len(self.g.players[0].hand), 3)
        self.assertNotIn(0, self.g.uno_open)

    def test_uno_atomic_declaration(self):
        self.g.players[0].hand = [self.c('blue', '1')]
        self.play('2', declare=True)
        self.assertNotIn(0, self.g.uno_open)

    def test_uno_button(self):
        self.g.players[0].hand = [self.c('blue', '1')]
        self.play('2')
        self.g.act(0, dict(op='uno'))
        self.assertNotIn(0, self.g.uno_open)

    def test_uno_window_closes_on_next_action(self):
        self.g.players[0].hand = [self.c('blue', '1')]
        self.play('2')
        self.play('3', seat=1)
        with self.assertRaises(RuleError):
            self.g.act(2, dict(op='catch', target=0))

    def test_swapped_single_opens_uno(self):
        self.g.players[0].hand = [self.c('blue', '1')]
        self.play('7', target=1, declare=True)
        self.assertIn(1, self.g.uno_open)
        self.assertNotIn(0, self.g.uno_open)

    def test_private_view(self):
        view = self.g.view(0)
        self.assertNotIn('deck', view)
        for p in view['players']:
            self.assertNotIn('hand', p)
        self.assertEqual({c['uid'] for c in view['hand']}, {c.uid for c in self.g.players[0].hand})

    def test_score(self):
        self.g.players[1].hand = [self.c('red', '9'), self.c('blue', 'skip'), self.c('wild', 'draw10')]
        self.g.players[2].out = True
        self.g._win(0)
        self.assertEqual(self.g.score, 329)

    def test_auto_sort(self):
        self.g.players[0].hand = [self.c('wild', 'draw10'), self.c('blue', '1'), self.c('red', '9'), self.c('red', '1')]
        self.assertEqual([(c['color'], c['kind']) for c in self.g.view(0)['hand']],
                         [('red', '1'), ('red', '9'), ('blue', '1'), ('wild', 'draw10')])

    def test_random_full_games_and_card_conservation(self):
        for n in range(2, 7):
            for seed in range(40):
                g = Game([str(i) for i in range(n)], bots=range(n), seed=seed)
                for turn in range(3000):
                    cards = g.deck + g.discard + g.retired + [c for p in g.players for c in p.hand]
                    self.assertEqual(len(cards), 168)
                    self.assertEqual(len({c.uid for c in cards}), 168)
                    self.assertTrue(all(len(p.hand) < 36 for p in g.players))
                    if g.winner is not None:
                        break
                    self.assertIn(g.current, g.active())
                    g.act(g.current, g.bot_action(g.current))
                self.assertIsNotNone(g.winner, f'{n} 人 seed={seed} 未能结束')


if __name__ == '__main__':
    unittest.main()
