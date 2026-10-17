"""无情版规则引擎：纯 Python，与界面和网络完全分离，便于单元测试。

所有客户端提交的动作都必须经过这里验证。牌用唯一编号标识，不能凭
客户端传来的颜色/类型信任一张牌。服务器只向每人发送自己的手牌。
"""
from dataclasses import dataclass, asdict
from collections import Counter
import random
import uuid
import time

COLORS = ('red', 'yellow', 'green', 'blue')
COLOR_NAMES = dict(zip(COLORS, ('红', '黄', '绿', '蓝')))
COLOR_NAMES['wild'] = '万能'
LABELS = {'skip': '跳过', 'reverse': '反转', 'discard': '同色全弃',
          'skip_all': '跳过一轮', 'draw2': '+2', 'draw4': '+4',
          'reverse4': '反转+4', 'draw6': '+6', 'draw10': '+10',
          'roulette': '颜色轮盘'}
DRAW = {'draw2': 2, 'draw4': 4, 'reverse4': 4, 'draw6': 6, 'draw10': 10}
ORDER = [str(i) for i in range(10)] + list(LABELS)


@dataclass(frozen=True)
class Card:
    uid: int
    color: str
    kind: str

    @property
    def label(self):
        return COLOR_NAMES[self.color] + ' ' + LABELS.get(self.kind, self.kind)

    def public(self):
        return {**asdict(self), 'label': self.label}


@dataclass
class Player:
    name: str
    hand: list
    out: bool = False
    bot: bool = False
    finished: bool = False
    death_count: int = 0


def make_deck():
    """168 张：每色 36 张，万能牌 24 张。数量集中定义，方便修改。"""
    specs = []
    for color in COLORS:
        for number in range(10):
            specs.extend([(color, str(number))] * 2)
        for kind, count in [('draw2', 3), ('draw4', 2), ('skip', 3),
                            ('reverse', 3), ('discard', 3), ('skip_all', 2)]:
            specs.extend([(color, kind)] * count)
    for kind, count in [('reverse4', 8), ('draw6', 4), ('draw10', 4), ('roulette', 8)]:
        specs.extend([('wild', kind)] * count)
    return [Card(i, *spec) for i, spec in enumerate(specs)]


class RuleError(ValueError):
    """可直接显示给玩家的合法性错误，不应导致服务器退出。"""


class Game:
    def __init__(self, names, bots=(), seed=None, end_remaining=1):
        if not 2 <= len(names) <= 6:
            raise RuleError('需要 2～6 位玩家。')
        if type(end_remaining) is not int or not 1 <= end_remaining < len(names):
            raise RuleError('结束人数须为 1 到总人数减 1。')
        self.end_remaining = end_remaining
        self.round_id = uuid.uuid4().hex
        self.finish_order = []
        self.death_order = []
        self.ranking = []
        self.recent = []
        self.draw_chain = []
        self.draw_event = None
        self.draw_serial = 0
        self.effects = []
        self.effect_serial = 0
        self.rng = random.Random(seed)
        self.players = [Player(n, [], bot=i in bots) for i, n in enumerate(names)]
        self.deck = make_deck()
        self.rng.shuffle(self.deck)
        self.discard = []
        self.retired = []  # 淘汰手牌留到下次洗牌才回收。
        self.current = 0
        self.direction = 1
        self.pending = 0
        self.last_draw = 0
        self.roulette = False
        self.forced = None  # 连抽后只能打出刚抽到的可用牌。
        self.uno_open = set()
        self.winner = None
        self.score = 0
        self.log = []
        self.revealed = []
        self.revision = 0
        for _ in range(7):
            for p in self.players:
                p.hand.append(self.deck.pop())
        # 起始牌的 0/7 不触发效果；功能牌跳过，仍保留在弃牌堆。
        while True:
            c = self.deck.pop()
            self.discard.append(c)
            if c.kind.isdigit():
                break
        self.color = c.color
        self.note('每人 7 张牌，游戏开始。')
        for seat in range(len(self.players)):
            self.emit('draw',seat=seat,count=7)

    def emit(self, kind, **data):
        """只传动画需要的公开数据；抽牌事件不含牌面或牌堆顺序。"""
        self.effect_serial += 1
        self.effects.append(dict(id=self.effect_serial,kind=kind,**data))
        self.effects = self.effects[-64:]

    def note(self, text):
        self.log.append(text)
        self.log = self.log[-80:]

    def active(self):
        return [i for i, p in enumerate(self.players) if not p.out]

    def next_seat(self, seat, steps=1):
        for _ in range(steps):
            for _ in self.players:
                seat = (seat + self.direction) % len(self.players)
                if not self.players[seat].out:
                    break
        return seat

    def _win(self, seat):
        """清空手牌先退场，整局仅在剩余人数达到设置后结算。"""
        if seat not in self.finish_order:
            self.finish_order.append(seat)
            self.players[seat].finished = True
            self.players[seat].out = True
            self.uno_open.discard(seat)
            self.note(f'{self.players[seat].name} 第 {len(self.finish_order)} 个清牌获胜，退场观战。')
        if self.current == seat:
            self.current = self.next_seat(seat)
        self._end_if_needed()

    def _end_if_needed(self):
        if len(self.active()) > self.end_remaining:
            return
        # 同手牌数使用并列名次；死亡者全部排在存活者后，晚死亡者靠前。
        survivors = sorted(self.active(), key=lambda i: (len(self.players[i].hand), i))
        ordered = self.finish_order + survivors + list(reversed(self.death_order))
        self.ranking = []
        last_count, last_rank = None, None
        for index, i in enumerate(ordered):
            p = self.players[i]
            kind = 'finished' if p.finished else 'dead' if p.out else 'survived'
            rank = index + 1
            if kind == 'survived' and last_count == len(p.hand):
                rank = last_rank
            last_count = len(p.hand) if kind == 'survived' else None
            last_rank = rank
            self.ranking.append(dict(seat=i, name=p.name, rank=rank, status=kind,
                                     count=p.death_count if kind == 'dead' else len(p.hand)))
        self.winner = ordered[0]
        self.uno_open.clear()
        self.score = sum(250 if p.out and not p.finished else sum(
            int(c.kind) if c.kind.isdigit() else 50 if c.color == 'wild' else 20
            for c in p.hand) for i, p in enumerate(self.players) if i != self.winner)
        self.note(f'场上剩余 {len(self.active())} 人，达到结束条件，进入领奖台。')

    def _take(self, seat):
        """35 张仍存活，第 36 张立即爆炸；保留死亡时牌数供结算。"""
        if not self.deck:
            self.deck = self.discard[:-1] + self.retired
            self.discard = self.discard[-1:]
            self.retired = []
            self.rng.shuffle(self.deck)
            self.note('抽牌堆用尽，回收弃牌及已淘汰手牌。')
        if not self.deck:
            self.note('牌暂时全部在玩家手中，无牌可抽，本次抽牌停止。')
            return None
        c = self.deck.pop()
        p = self.players[seat]
        p.hand.append(c)
        # 同一原子动作中的连续抽牌合并为一个数量事件，保持精确数量。
        if self.effects and self.effects[-1]['kind']=='draw' and self.effects[-1].get('batch')==self.revision and self.effects[-1]['seat']==seat:
            self.effects[-1]['count']+=1
        else:
            self.emit('draw',seat=seat,count=1,batch=self.revision)
        if len(p.hand) >= 36:
            p.out = True
            p.death_count = len(p.hand)
            self.death_order.append(seat)
            self.retired.extend(p.hand)
            p.hand = []
            self.uno_open.discard(seat)
            self.note(f'{p.name} 达到 36 张，爆炸死亡！')
            self._end_if_needed()
        return c

    def matches(self, c):
        if self.pending:
            # 比较上一张罚牌，绝不能比较累计罚牌张数。
            return DRAW.get(c.kind, 0) >= self.last_draw
        return c.color == 'wild' or c.color == self.color or c.kind == self.discard[-1].kind

    def is_admin(self, seat):
        """本地聚会用作者模式，由服务器按座位昵称判定。"""
        return self.players[seat].name.strip().casefold() in ('admin','op')

    def legal(self, seat):
        if self.is_admin(seat) and not self.players[seat].out and self.winner is None:
            return [c.uid for c in self.players[seat].hand]
        if self.winner is not None or seat != self.current or self.roulette or self.players[seat].out:
            return []
        return [c.uid for c in self.players[seat].hand
                if self.matches(c) and (self.forced is None or c.uid == self.forced)]

    def act(self, seat, action):
        """动作先验证再修改；无效动作不关闭抓漏喊窗口，也不消耗回合。"""
        if isinstance(action,dict) and action.get('op')=='shout' and type(seat) is int and 0<=seat<len(self.players):
            if len(self.players[seat].hand)==1 and not self.players[seat].out:
                self.uno_open.discard(seat)
            self.emit('uno',seat=seat)
            return  # 表情不推进回合，不改变版本号或电脑等待时间。
        if self.winner is not None:
            raise RuleError('本局已结束。')
        if not isinstance(action, dict):
            raise RuleError('动作格式错误。')
        if not 0 <= seat < len(self.players) or self.players[seat].out:
            raise RuleError('已淘汰的玩家只能观战。')
        op = action.get('op')
        p = self.players[seat]
        if op == 'forge':
            if not self.is_admin(seat):
                raise RuleError('只有作者模式可以造牌。')
            kind=action.get('kind')
            if kind not in ('reverse4','draw6','draw10','roulette'):
                raise RuleError('请选择一种黑色功能牌。')
            # 独立递增编号，生成的牌仍进入真实牌堆/手牌和死亡判定。
            self.forge_uid=getattr(self,'forge_uid',100000)+1
            self.deck.append(Card(self.forge_uid,'wild',kind))
            self._take(seat)
            self.note(f'{p.name} 生成了一张{LABELS[kind]}。')
        elif op == 'uno':
            if len(p.hand) != 1:
                raise RuleError('剩一张手牌时才能喊牌。')
            self.uno_open.discard(seat)
            self.note(f'{p.name} 喊：剩一张！')
            self.emit('uno',seat=seat)
        elif op == 'catch':
            target = action.get('target')
            if type(target) is not int or target == seat or target not in self.uno_open:
                raise RuleError('该玩家没有可抓的漏喊。')
            self.uno_open.discard(target)
            for _ in range(2):
                self._take(target)
            self.note(f'{p.name} 抓到 {self.players[target].name} 漏喊，罚抽 2 张。')
        else:
            if seat != self.current and not (self.is_admin(seat) and op=='play'):
                raise RuleError('还没轮到你。')
            if self.roulette:
                if op != 'color' or action.get('color') not in COLORS:
                    raise RuleError('请先选择颜色轮盘的目标颜色。')
                self.uno_open.clear()
                self._roulette(seat, action['color'])
            elif op == 'play':
                uid = action.get('card')
                if type(uid) is not int or uid not in self.legal(seat):
                    raise RuleError('这张牌现在不能出。')
                c = next(c for c in p.hand if c.uid == uid)
                if c.color == 'wild' and action.get('color') not in COLORS:
                    raise RuleError('请选择出牌后的颜色。')
                target = action.get('target')
                if c.kind == '7' and len(p.hand) > 1:
                    if type(target) is not int or target == seat or target not in self.active():
                        raise RuleError('请选择一位未淘汰的换牌对象。')
                self.uno_open.clear()
                if self.is_admin(seat) and c.kind not in DRAW:
                    self.pending=self.last_draw=0
                    self.draw_chain=[]
                self._play(seat, c, action)
            elif op == 'draw':
                if not self.pending and self.legal(seat):
                    raise RuleError('有可出的牌，请先出牌。')
                self.uno_open.clear()
                self._draw_turn(seat)
            else:
                raise RuleError('无法识别的操作。')
        self.revision += 1

    def _play(self, seat, c, action):
        p = self.players[seat]
        p.hand.remove(c)
        self.forced = None
        self.revealed = []
        if c.kind == 'discard':
            extra = [x for x in p.hand if x.color == c.color]
            self.discard.extend(extra)
            p.hand = [x for x in p.hand if x.color != c.color]
            self.note(f'{p.name} 同时弃掉 {len(extra)} 张同色牌；附带牌不触发效果。')
        self.discard.append(c)
        if c.color != 'wild':
            self.color = c.color
        else:
            self.color = action['color']
            self.emit('color',seat=seat,color=self.color)
            self.visual_until = time.monotonic()+1
        self.note(f'{p.name} 打出 {c.label}。')
        self.recent.append(dict(c.public(),gold=self.is_admin(seat)))
        self.recent = self.recent[-5:]
        finishing = not p.hand
        changed = {seat}
        if c.kind == '7' and not finishing:
            target = action['target']
            p.hand, self.players[target].hand = self.players[target].hand, p.hand
            changed.add(target)
            self.note(f'{p.name} 与 {self.players[target].name} 交换了全部手牌。')
            self.emit('swap',seat=seat,moves=[[seat,target,len(self.players[target].hand)],
                                           [target,seat,len(p.hand)]])
        elif c.kind == '0' and not finishing:
            old = {i: self.players[i].hand for i in self.active()}
            for i, hand in old.items():
                self.players[self.next_seat(i)].hand = hand
            changed.update(old)
            self.note('所有未淘汰玩家沿当前方向传递手牌。')
            self.emit('pass',seat=seat,moves=[[i,self.next_seat(i),len(hand)] for i,hand in old.items()])
        if c.kind in ('reverse', 'reverse4'):
            self.direction *= -1
        target = self.next_seat(seat)
        if c.kind in ('skip_all',) or (c.kind in ('reverse', 'reverse4') and len(self.active()) == 2):
            target = seat
        elif c.kind == 'skip':
            target = self.next_seat(seat, 2)
        if c.kind in DRAW:
            self.draw_chain.append(c.public())
            self.pending += DRAW[c.kind]
            self.last_draw = DRAW[c.kind]
            self.note(f'累计罚抽 {self.pending} 张；可叠加 +{self.last_draw} 或更高。')
        self.current = target
        if c.kind == 'roulette':
            self.note(f'{p.name} 指定轮盘颜色：{COLOR_NAMES[self.color]}。')
            self._roulette(target,self.color)
        if finishing:
            self._win(seat)
            return
        for i in changed:
            if len(self.players[i].hand) == 1:
                self.uno_open.add(i)
        if action.get('declare') is True and len(p.hand) == 1:
            self.uno_open.discard(seat)
            self.note(f'{p.name} 喊：剩一张！')
            self.emit('uno',seat=seat)

    def _draw_turn(self, seat):
        count = 0
        if self.pending:
            total = self.pending
            for _ in range(total):
                if self._take(seat) is None:
                    break
                count += 1
                if self.players[seat].out:
                    break
            self.pending = self.last_draw = 0
            self.draw_chain = []
            self.current = self.next_seat(seat)
            self.note(f'{self.players[seat].name} 接受罚牌，抽了 {count} 张并跳过回合。')
        else:
            # 普通抽牌仅一张。可出则锁定这一张，否则立即转给下一位。
            # 罚牌和轮盘保留各自抽牌规则，不进入此分支。
            c = self._take(seat)
            playable = c is not None and not self.players[seat].out and self.matches(c)
            self.draw_serial += 1
            self.draw_event = dict(serial=self.draw_serial, seat=seat,
                                   card=c.public() if c else None, playable=playable)
            if playable:
                self.forced = c.uid
                self.note(f'{self.players[seat].name} 抽到可用牌，必须立即打出。')
            else:
                self.forced = None
                self.current = self.next_seat(seat)
                self.note(f'{self.players[seat].name} 抽牌后结束回合。')

    def _roulette(self, seat, color):
        self.color = color
        self.revealed = []
        first_event = self.effect_serial
        while True:
            c = self._take(seat)
            if c is None:
                break
            self.revealed.append(c.public())
            if self.players[seat].out or c.color == color:
                break
        # 将这次抽牌的普通背面动画替换为明牌逐张展示，收齐后统一飞行。
        self.effects = [e for e in self.effects if e['id']<=first_event or e['kind']!='draw']
        self.emit('reveal',seat=seat,cards=list(self.revealed),count=len(self.revealed))
        self.visual_until = time.monotonic()+1+len(self.revealed)*.10+.85
        self.note(f'{self.players[seat].name} 抽到{COLOR_NAMES[color]}色为止，轮盘公开：' +
                  '、'.join(c['label'] for c in self.revealed))
        self.roulette = False
        self.current = self.next_seat(seat)

    def view(self, seat):
        """服务器定制视图：对手手牌、牌堆顺序永远不进入消息。"""
        return {'players': [{'name': p.name, 'admin': self.is_admin(i), 'count': len(p.hand), 'out': p.out,
                             'bot': p.bot, 'finished': p.finished, 'death_count': p.death_count} for i,p in enumerate(self.players)],
                'recent': self.recent, 'draw_chain': self.draw_chain,
                'round_id': self.round_id,
                'effects': [dict(e) for e in self.effects],
                'draw_event': ({**self.draw_event,
                                'card': self.draw_event['card'] if self.draw_event['seat'] == seat else None}
                               if self.draw_event else None),
                'end_remaining': self.end_remaining, 'ranking': self.ranking,
                'finish_order': self.finish_order, 'death_order': self.death_order,
                'hand': [c.public() for c in sorted(self.players[seat].hand,
                          key=lambda c: ((*COLORS, 'wild').index(c.color), ORDER.index(c.kind), c.uid))],
                'legal': self.legal(seat), 'current': self.current, 'direction': self.direction,
                'top': self.discard[-1].public(), 'color': self.color,
                'pending': self.pending, 'last_draw': self.last_draw,
                'roulette': self.roulette, 'forced': self.forced,
                'winner': self.winner, 'score': self.score,
                'uno_open': sorted(self.uno_open), 'log': self.log,
                'revealed': self.revealed, 'deck_count': len(self.deck),
                'revision': self.revision}

    def bot_action(self, seat):
        """基础电脑策略：优先全弃、多牌换少牌，保留部分万能牌救场。"""
        p = self.players[seat]
        if seat in self.uno_open:
            return {'op': 'uno'}
        others = self.uno_open - {seat}
        if others:
            return {'op': 'catch', 'target': min(others)}
        color_counts = Counter(c.color for c in p.hand if c.color != 'wild')
        color = max(COLORS, key=lambda c: color_counts[c])
        if self.roulette:
            return {'op': 'color', 'color': self.rng.choice(COLORS)}
        legal = self.legal(seat)
        if not legal:
            return {'op': 'draw'}
        def priority(c):
            if c.kind == 'discard':
                return 100 + color_counts[c.color]
            if c.kind == '7' and len(p.hand) > min(len(self.players[i].hand) for i in self.active()):
                return 90
            return (20 if c.color != 'wild' else 0) + DRAW.get(c.kind, 0)
        c = max((c for c in p.hand if c.uid in legal), key=priority)
        target = min((i for i in self.active() if i != seat), key=lambda i: len(self.players[i].hand))
        return {'op': 'play', 'card': c.uid, 'color': color, 'target': target, 'declare': True}
