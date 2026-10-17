"""标准库 TCP + 换行分隔 JSON；服务器权威判定，支持断线原席重连。

仅用于可信局域网：房间码限制误入，不提供公网级 TLS 或账号系统。
规则操作受一把锁保护，每个快照按座位独立生成。客户端接收线程只向
队列写入，Tk 主线程通过轮询队列更新窗口，避免跨线程操作界面。
"""
import json
import queue
import secrets
import socket
import socketserver
import threading
import time
from engine import Game, RuleError

PROTOCOL = 6
BOT_DELAY = 1.5
MAX_MESSAGE = 65536


def encode(message):
    return (json.dumps(message, ensure_ascii=False) + '\n').encode('utf-8')


class Room(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address=('0.0.0.0', 8765)):
        self.lock = threading.RLock()
        self.code = f'{secrets.randbelow(1000000):06d}'
        self.owner = secrets.token_urlsafe(24)
        self.seats = []
        self.game = None
        self.running = True
        self.next_bot = time.monotonic() + 1
        super().__init__(address, Peer)

    def launch(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()
        threading.Thread(target=self._bots, daemon=True).start()

    def close(self):
        self.running = False
        with self.lock:
            for s in self.seats:
                peer = s.get('peer')
                if peer:
                    peer.send({'type': 'closed', 'message': '房主已关闭房间。'})
                    try:
                        peer.request.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
        self.shutdown()
        self.server_close()

    def paused(self):
        return self.game is not None and self.game.winner is None and any(
            not s['bot'] and s['peer'] is None and not self.game.players[i].out
            for i, s in enumerate(self.seats))

    def snapshot(self, seat):
        return {'type': 'state', 'seat': seat, 'host': self.seats[seat]['owner'],
                'paused': self.paused(),
                'members': [{'name': s['name'], 'bot': s['bot'],
                             'connected': s['bot'] or s['peer'] is not None,
                             'total': s['total']} for s in self.seats],
                'game': self.game.view(seat) if self.game else None}

    def broadcast(self):
        for i, s in enumerate(self.seats):
            if s['peer']:
                s['peer'].send(self.snapshot(i))

    def join(self, peer, msg):
        with self.lock:
            if msg.get('protocol') != PROTOCOL or msg.get('code') != self.code:
                raise RuleError('房间码或程序版本不匹配。')
            token = msg.get('token')
            for i, s in enumerate(self.seats):
                if token and token == s['token'] and not s['bot']:
                    if s['peer'] is not None:
                        raise RuleError('这个座位仍然在线。')
                    s['peer'] = peer
                    peer.seat = i
                    peer.send({'type': 'welcome', 'token': s['token'], 'seat': i})
                    self.broadcast()
                    return
            if self.game is not None:
                raise RuleError('游戏已经开始，仅支持原窗口断线重连。')
            if len(self.seats) >= 6:
                raise RuleError('房间已满。')
            name = msg.get('name')
            if not isinstance(name, str) or not name.strip() or len(name) > 16 or any(ord(c) < 32 for c in name):
                raise RuleError('昵称需要 1～16 个可见字符。')
            name = name.strip()
            if any(s['name'] == name for s in self.seats):
                raise RuleError('昵称已被使用。')
            owner = msg.get('owner') == self.owner
            if not self.seats and not owner:
                raise RuleError('请等待房主入座。')
            token = secrets.token_urlsafe(24)
            peer.seat = len(self.seats)
            self.seats.append(dict(name=name, token=token, owner=owner,
                                   peer=peer, bot=False, total=0))
            peer.send({'type': 'welcome', 'token': token, 'seat': peer.seat})
            self.broadcast()

    def handle_action(self, peer, msg):
        with self.lock:
            seat = peer.seat
            op = msg.get('op')
            is_owner = self.seats[seat]['owner']
            if op=='shout':
                if self.game:
                    self.game.act(seat,{'op':'shout'})
                    self.broadcast()
                else:
                    for s in self.seats:
                        if s['peer']:
                            s['peer'].send({'type':'shout','seat':seat})
                return
            if op in ('add_bot', 'remove_bot', 'start', 'takeover') and not is_owner:
                raise RuleError('只有房主可以执行此操作。')
            if op in ('add_bot', 'remove_bot'):
                if self.game is not None:
                    raise RuleError('开始游戏后无法调整座位。')
                if op == 'add_bot':
                    if len(self.seats) >= 6:
                        raise RuleError('房间已满。')
                    n = 1
                    while any(s['name'] == f'电脑 {n}' for s in self.seats):
                        n += 1
                    self.seats.append(dict(name=f'电脑 {n}', token=None, owner=False,
                                           peer=None, bot=True, total=0))
                else:
                    # 只移除末尾电脑，保证在线人类座位编号不发生移动。
                    if not self.seats or not self.seats[-1]['bot']:
                        raise RuleError('只可移除房间末尾的电脑玩家。')
                    self.seats.pop()
            elif op == 'start':
                if self.game is not None and self.game.winner is None:
                    raise RuleError('当前对局尚未结束。')
                if any(not s['bot'] and s['peer'] is None for s in self.seats):
                    raise RuleError('有玩家离线，请等待重连或交给电脑接管。')
                self.game = Game([s['name'] for s in self.seats],
                                 bots=[i for i, s in enumerate(self.seats) if s['bot']],
                                 end_remaining=msg.get('end_remaining', 1))
            elif op == 'takeover':
                target = msg.get('target')
                if type(target) is not int or not 0 <= target < len(self.seats):
                    raise RuleError('座位无效。')
                s = self.seats[target]
                if s['owner'] or s['bot'] or s['peer'] is not None:
                    raise RuleError('只能接管离线朋友的座位。')
                s['bot'], s['token'] = True, None
                if self.game:
                    self.game.players[target].bot = True
            else:
                if self.game is None:
                    raise RuleError('请等待房主开始游戏。')
                if self.paused():
                    raise RuleError('有玩家断线，对局暂停。')
                if time.monotonic() < getattr(self.game,'visual_until',0):
                    raise RuleError('正在展示选色或轮盘明牌，请稍候。')
                # 版本号防止双击或过期弹窗重复提交同一个回合。
                if msg.get('revision') != self.game.revision:
                    raise RuleError('牌桌已更新，请重新操作。')
                self.game.act(seat, msg)
                self._score()
            self.next_bot = time.monotonic() + BOT_DELAY
            self.broadcast()

    def _score(self):
        if self.game.winner is not None and not getattr(self.game, '_counted', False):
            self.seats[self.game.winner]['total'] += self.game.score
            self.game._counted = True

    def _bots(self):
        while self.running:
            time.sleep(0.15)
            with self.lock:
                g = self.game
                if not g or g.winner is not None or self.paused() or time.monotonic() < max(self.next_bot,getattr(g,'visual_until',0)):
                    continue
                if not self.seats[g.current]['bot']:
                    continue
                try:
                    g.act(g.current, g.bot_action(g.current))
                    self._score()
                    self.broadcast()
                except RuleError as exc:
                    g.note('电脑操作异常：' + str(exc))
                self.next_bot = time.monotonic() + BOT_DELAY


class Peer(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.seat = None
        self.send_lock = threading.Lock()
        self.request.settimeout(10)  # 握手必须及时完成。

    def send(self, msg):
        try:
            with self.send_lock:
                self.request.sendall(encode(msg))
        except OSError:
            pass

    def handle(self):
        try:
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE or not raw.endswith(b'\n'):
                return
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                raise RuleError('无效的握手消息。')
            self.server.join(self, msg)
            self.request.settimeout(None)
            last = 0
            while True:
                raw = self.rfile.readline(MAX_MESSAGE + 1)
                if not raw or len(raw) > MAX_MESSAGE or not raw.endswith(b'\n'):
                    break
                # 限制单个客户端的操作频率；常规点击不受影响。
                now = time.monotonic()
                if now - last < 0.05:
                    continue
                last = now
                try:
                    msg = json.loads(raw)
                    if not isinstance(msg, dict):
                        raise RuleError('无效的消息。')
                    self.server.handle_action(self, msg)
                except (RuleError, ValueError, TypeError) as exc:
                    self.send({'type': 'error', 'message': str(exc)})
        except (RuleError, ValueError, TypeError) as exc:
            self.send({'type': 'error', 'message': str(exc)})
        except OSError:
            pass
        finally:
            with self.server.lock:
                if self.seat is not None and self.server.seats[self.seat]['peer'] is self:
                    self.server.seats[self.seat]['peer'] = None
                    self.server.broadcast()


class Client:
    def __init__(self):
        self.events = queue.Queue()
        self.sock = None
        self.token = None
        self.connected = False
        self.generation = 0

    def connect(self, host, port, name, code, owner=None):
        self.generation += 1
        generation = self.generation
        def worker():
            sock = None
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.settimeout(None)
                if generation != self.generation:
                    sock.close()
                    return
                self.sock = sock
                self.connected = True
                sock.sendall(encode(dict(protocol=PROTOCOL, name=name, code=code,
                                         owner=owner, token=self.token)))
                with sock.makefile('rb') as stream:
                    while generation == self.generation:
                        raw = stream.readline(MAX_MESSAGE + 1)
                        if not raw:
                            break
                        if len(raw) > MAX_MESSAGE:
                            raise ValueError('服务器消息过大。')
                        msg = json.loads(raw)
                        if msg.get('type') == 'welcome':
                            self.token = msg['token']
                        self.events.put(msg)
            except (OSError, ValueError) as exc:
                if generation == self.generation:
                    self.events.put({'type': 'error', 'message': f'连接失败：{exc}'})
            finally:
                if sock:
                    sock.close()
                if generation == self.generation:
                    self.connected = False
                    self.events.put({'type': 'disconnected'})
        threading.Thread(target=worker, daemon=True).start()

    def send(self, msg):
        if not self.connected or self.sock is None:
            raise OSError('连接已断开，请先重连。')
        self.sock.sendall(encode(msg))

    def close(self):
        self.generation += 1
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        self.sock = None
