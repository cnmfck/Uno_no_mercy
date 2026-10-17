"""通过真实回环 TCP 测试多客户端、权限、隐私、重连和完整对局。"""
import queue
import time
import unittest
from network import Room, Client


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(('127.0.0.1', 0))
        self.room.launch()
        self.clients = []
        self.host = self.connect('房主', owner=self.room.owner)
        self.wait(self.host, lambda m: m['type'] == 'state')

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.room.close()

    def connect(self, name, owner=None, code=None):
        c = Client()
        self.clients.append(c)
        c.connect('127.0.0.1', self.room.server_address[1], name,
                  self.room.code if code is None else code, owner)
        return c

    def wait(self, client, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        observed = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                msg = client.events.get(timeout=remaining)
            except queue.Empty:
                break
            observed.append({
                'type': msg.get('type'),
                'message': msg.get('message'),
                'revision': (msg.get('game') or {}).get('revision'),
            })
            if predicate(msg):
                return msg
        self.fail(f'No matching TCP response within {timeout}s; '
                  f'connected={client.connected}; recent messages={observed[-8:]}')

    def state(self, c, predicate=lambda s: True):
        return self.wait(c, lambda m: m['type'] == 'state' and predicate(m))

    def command(self, c, **msg):
        # The server discards requests received less than 50 ms apart.
        # Allow a wider margin for OS scheduling and TCP delivery timing.
        time.sleep(.15)
        c.send(msg)

    def start_two(self):
        friend = self.connect('朋友')
        self.state(friend)
        self.command(self.host, op='start')
        self.state(self.host, lambda s: s['game'] is not None)
        self.state(friend, lambda s: s['game'] is not None)
        return friend

    def test_two_clients_private_hands(self):
        friend = self.start_two()
        with self.room.lock:
            a, b = self.room.snapshot(0), self.room.snapshot(1)
        self.assertEqual(a['seat'], 0)
        self.assertEqual(b['seat'], 1)
        self.assertFalse({c['uid'] for c in a['game']['hand']} & {c['uid'] for c in b['game']['hand']})
        self.assertTrue(all('hand' not in p for p in a['game']['players']))

    def test_wrong_room_code_rejected(self):
        bad = self.connect('陌生人', code='invalid')
        error = self.wait(bad, lambda m: m['type'] == 'error')
        self.assertIn('房间码', error['message'])
        self.assertEqual(len(self.room.seats), 1)

    def test_nonhost_cannot_start(self):
        friend = self.connect('朋友')
        self.state(friend)
        self.command(friend, op='start')
        self.wait(friend, lambda m: m['type'] == 'error')
        self.assertIsNone(self.room.game)

    def test_reconnect_preserves_seat_hand_and_unpauses(self):
        friend = self.start_two()
        hand = self.room.game.view(1)['hand']
        token = friend.token
        friend.close()
        self.state(self.host, lambda s: s['paused'])
        friend.connect('127.0.0.1', self.room.server_address[1], '朋友', self.room.code)
        state = self.state(friend, lambda s: not s['paused'])
        self.assertEqual(friend.token, token)
        self.assertEqual(state['seat'], 1)
        self.assertEqual(state['game']['hand'], hand)

    def test_takeover(self):
        friend = self.start_two()
        friend.close()
        self.state(self.host, lambda s: s['paused'])
        self.command(self.host, op='takeover', target=1)
        s = self.state(self.host, lambda s: not s['paused'] and s['members'][1]['bot'])
        self.assertTrue(s['game']['players'][1]['bot'])

    def test_stale_action_rejected(self):
        self.start_two()
        self.command(self.host, op='draw', revision=-1)
        error = self.wait(self.host, lambda m: m['type'] == 'error')
        self.assertIn('更新', error['message'])

    def test_lobby_bots_and_next_round(self):
        self.command(self.host, op='add_bot')
        self.state(self.host, lambda s: len(s['members']) == 2)
        self.command(self.host, op='remove_bot')
        self.state(self.host, lambda s: len(s['members']) == 1)
        self.command(self.host, op='add_bot')
        self.state(self.host, lambda s: len(s['members']) == 2)
        self.command(self.host, op='start')
        self.state(self.host, lambda s: s['game'] is not None)
        with self.room.lock:
            self.room.game._win(0)
            self.room._score()
            score = self.room.seats[0]['total']
        self.command(self.host, op='start')
        s = self.state(self.host, lambda s: s['game']['winner'] is None and s['members'][0]['total'] == score)
        self.assertEqual(len(s['game']['hand']), 7)

    def test_complete_game_through_tcp(self):
        self.start_two()
        for _ in range(1500):
            with self.room.lock:
                g = self.room.game
                if g.winner is not None:
                    break
                seat, revision = g.current, g.revision
                action = g.bot_action(seat)
                hold = max(0,getattr(g,'visual_until',0)-time.monotonic())
            # 真人端也必须等待选色/明牌展示结束才能发送下一步动作。
            if hold:
                time.sleep(hold+.02)
            # 两个测试客户端分别通过网络发送策略动作；服务器正常判定。
            self.command(self.clients[seat], **action, revision=revision)
            self.state(self.clients[seat], lambda s: s['game']['revision'] > revision)
        self.assertIsNotNone(self.room.game.winner)


if __name__ == '__main__':
    unittest.main()
