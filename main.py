"""桌面入口。运行：python main.py（Python 3.10+，只用标准库）。

界面只负责展示和收集选择；能否出牌、交换和罚牌都由服务器判定。
绘制使用 Tk Canvas，无需下载图片、字体、音效或任何网络资源。
"""
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from engine import COLORS, COLOR_NAMES, LABELS, ORDER
from network import Room, Client
from visuals import draw_scene, draw_podium
from card_art import paint_card, pile_hit
from effects import Effects, PLAYER_COLORS, tint, seat_color
from color_wheel import open_wheel

BG = '#101827'
PANEL = '#1b293b'
TABLE = '#143c3e'
TEXT = '#edf3f9'
MUTED = '#a9bbca'
GOLD = '#ffd36a'
PALETTE = {'red': '#c73f50', 'yellow': '#e6b842', 'green': '#258568',
           'blue': '#356ac0', 'wild': '#30324a'}
HELP = '''玩法与操作

本程序支持 2～6 人：同一局域网的多台电脑，或一名真人搭配电脑玩家。
自动按红、黄、绿、蓝、万能排列手牌，每种颜色内按数字和功能排列。
金色描边、“可出”标签表示当前可出的牌；暗色牌仍可点击查看说明。
双击手牌或拖向中央出牌；普通抽牌点右侧牌堆。万能牌和 7 会弹出选择窗。

数字与功能牌
7：出牌后，与任选一名未淘汰玩家交换全部手牌。
0：所有未淘汰玩家沿当前方向传递全部手牌。
+2、+4：有颜色的罚牌；下家罚抽并跳过，允许叠加。
跳过：跳过下一位。反转：改变方向；双人局自己再出一次。
同色全弃：手里与此牌同色的牌全部放到它下面，附带牌不触发效果。
跳过一轮：跳过其他所有人，自己继续出牌。
反转+4：万能牌，先反转方向再罚 4；双人局由出牌者自己承担，可叠加。
+6、+10：万能罚牌，选择后续颜色，下家承担罚牌，可叠加。
颜色轮盘：出牌者选颜色，下家逐张公开抽牌至抽中该颜色，全部收下并跳过。
万能牌不算抽中颜色。公开的轮盘牌会显示在牌桌和记录中。

关键规则
叠加：只需不小于上一张罚牌数值，跨颜色也可叠加。例如 +4、+6 后，
累计罚 10，但仍可用 +6 继续。接受罚牌将跳过回合。
无法出牌时只抽一张；能出必须出，不能出就结束本回合。罚牌和轮盘规则保留。
达到 36 张爆炸死亡，35 张仍存活；死亡手牌在下一次洗牌时回收。
牌堆耗尽时保留桌面顶牌，其余弃牌和淘汰手牌重新洗牌。
清空手牌的玩家按先后顺序获胜退场。剩余人数达到房主设定才结算。
末张 0/7 清空即退场，不交出空手牌；其他末张功能牌仍触发效果。

喊牌与抓漏喊
手牌右侧 UNO 按钮随时可按，触发红字特效；剩一张时也会完成喊牌声明。
在右侧 UNO 按钮下方勾选“出牌同时喊 UNO”可随出牌声明；空格快捷喊牌。
未及时喊牌的玩家会显示“抓漏喊”；其他玩家可点击，让其罚抽 2 张。
网络版以服务器收到下一位有效出牌、抽牌或轮盘选择为窗口截止。
交换/传牌后新拿到单张手牌的玩家也需要喊牌。

断线与计分
有人断线会暂停对局；保留原窗口，点击“重连”回到原座位。
关闭客户端会丢失本机重连凭据。房主可让电脑永久接管离线座位。
房主程序关闭后房间结束。本程序不提供跨进程存档和公网匹配。
每局结算：对手数字面值、彩色功能牌 20、万能牌 50、每名淘汰者 250。
房间累计计分，房主可开始下一局；本版不强制在 1000 分终止房间。

规则边界
颜色轮盘结束后的有效颜色采用出牌者选定颜色。
罚牌过程中到 36 张即死亡，剩余未发惩罚不传给其他人。
领奖台：先清牌者在前，其次是存活者按手牌少到多（相同张数并列），
最后是死亡者（晚死亡者在前）。这是本程序的自定义规则。
以上数字化边界写在说明中，方便朋友们约定与修改。
此版本包含基础无情版全部功能牌，不包含另售扩展包。
本程序为非官方学习项目，牌面由代码绘制，无官方图片资源。
'''
DESCRIPTIONS = {
    '7': '交换双方全部手牌，随后按原顺序继续。',
    '0': '所有未淘汰玩家按当前方向传递手牌。',
    'skip': '下一位玩家跳过回合。',
    'reverse': '改变出牌方向；双人局由你继续。',
    'discard': '一次弃掉全部同色牌，附带牌不触发功能。',
    'skip_all': '跳过其余所有人，你再出一张。',
    'draw2': '下家罚抽 2 张；可用 +2 或更大罚牌叠加。',
    'draw4': '下家罚抽 4 张；可用 +4 或更大罚牌叠加。',
    'reverse4': '反转并罚抽 4 张。双人局先罚自己，可叠加。',
    'draw6': '选择颜色，下家罚抽 6 张；可继续叠加。',
    'draw10': '选择颜色，下家罚抽 10 张；仅 +10 能继续叠加。',
    'roulette': '你指定颜色，下家公开连抽直到命中，收牌并跳过。',
}


class App:
    def __init__(self, root):
        self.root = root
        root.bind('<KeyPress-space>',self._space_uno)
        root.bind_class('UnoShortcut','<KeyPress-space>',self._space_uno)
        root.bind_class('UnoShortcut','<KeyRelease-space>',lambda e:'break')
        self.last_space = 0
        self.hover_uid = None
        self.hand_hits = []
        self.avatar_widgets = {}
        self.fx = Effects(self)
        root.title('UNO NO MERCY')
        width = max(980, min(1180, root.winfo_screenwidth() - 80))
        height = max(680, min(820, root.winfo_screenheight() - 100))
        root.geometry(f'{width}x{height}')
        root.minsize(980, 680)
        root.configure(bg=BG)
        self.room = None
        self.client = None
        self.state = None
        self.connection = None
        self.selected = None
        self.drag_uid = None
        self.drag_active = False
        self.drag_over = False
        self.drag_ghost = None
        self.draw_since = 0
        self.seen_draw = None
        self.auto_forced = None
        self.end_remaining = tk.StringVar(value='1')
        self.effect_since = time.monotonic()
        self.death_since = 0
        self.death_names = []
        self.visual_round = None
        self.visual_last = None
        self.visual_deaths = []
        self.podium_round = None
        self.podium = None
        self.dialog = None
        self.practice_target = None
        self.name = tk.StringVar(value='玩家')
        self.host = tk.StringVar(value='192.168.1.100')
        self.port = tk.StringVar(value='8765')
        self.code = tk.StringVar()
        self.bots = tk.StringVar(value='3')
        self.declare = tk.BooleanVar(value=False)
        self.legal_first = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='创建房间，邀请朋友；也可以先和电脑练习。')
        self.connection_label = tk.StringVar()
        self._style()
        self.shell = tk.Frame(root, bg=BG)
        self.shell.pack(fill='both', expand=True, padx=22, pady=18)
        self._menu()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(80, self._poll)
        root.after(33, self._animate)

    def _style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 11), background=PANEL, foreground=TEXT)
        style.configure('TButton', padding=(13, 9), background='#30465e', borderwidth=0)
        style.map('TButton', background=[('active', '#42617e'), ('disabled', '#233143')],
                  foreground=[('disabled', '#708195')])
        style.configure('Accent.TButton', background='#b57926', foreground='white')
        style.map('Accent.TButton', background=[('active', '#cb923c'), ('disabled', '#554d40')])
        style.configure('TEntry', fieldbackground='#f5f7fa', foreground='#172538', padding=7)
        style.configure('TCombobox', fieldbackground='#f5f7fa', foreground='#172538')
        style.map('TCombobox', fieldbackground=[('readonly', '#f5f7fa')], foreground=[('readonly', '#172538')])
        style.configure('TCheckbutton', background=BG)
        style.map('TCheckbutton', background=[('active', BG)])

    def label(self, parent, text='', size=11, color=TEXT, bg=BG, **kw):
        return tk.Label(parent, text=text, bg=bg, fg=color,
                        font=('Microsoft YaHei UI', size), **kw)

    def _menu(self):
        for child in self.shell.winfo_children():
            child.destroy()
        header = tk.Frame(self.shell, bg=BG)
        header.pack(fill='x')
        self.label(header, 'UNO NO MERCY', 28).pack(side='left')
        self.label(header, '局域网 · 2—6 人 · 全功能牌', 12, MUTED).pack(side='left', padx=22)
        ttk.Button(header, text='玩法说明', command=self.help).pack(side='right')
        self.label(self.shell, '把朋友叫齐，牌桌就在这里。', 17, GOLD).pack(anchor='w', pady=(25, 15))
        row = tk.Frame(self.shell, bg=BG)
        row.pack(fill='x', pady=12)
        self.label(row, '你的昵称').pack(side='left', padx=(0, 12))
        ttk.Entry(row, textvariable=self.name, width=22).pack(side='left')
        cards = tk.Frame(self.shell, bg=BG)
        cards.pack(fill='both', expand=True, pady=15)
        cards.columnconfigure((0, 1), weight=1, uniform='menu')
        for i, title in enumerate(('创建房间', '加入朋友')):
            box = tk.Frame(cards, bg=PANEL, padx=25, pady=24)
            box.grid(row=0, column=i, sticky='nsew', padx=(0, 12) if i == 0 else (12, 0))
            self.label(box, title, 21, bg=PANEL).pack(anchor='w', pady=(0, 20))
            if i == 0:
                self.label(box, '房主运行服务器，也可以参加游戏。\n所有电脑连接同一个家庭网络或热点。',
                           11, MUTED, PANEL, justify='left').pack(anchor='w', pady=(0, 20))
                ttk.Button(box, text='创建局域网房间', style='Accent.TButton',
                           command=self.create).pack(fill='x', pady=8)
                self.label(box, '或者单人练习：电脑玩家数量', 11, MUTED, PANEL).pack(anchor='w', pady=(25, 8))
                ttk.Combobox(box, values=('1', '2', '3', '4', '5'), textvariable=self.bots,
                             state='readonly', width=8).pack(anchor='w')
                ttk.Button(box, text='开始电脑练习', command=lambda: self.create(True)).pack(fill='x', pady=12)
            else:
                for label, var in [('房主局域网地址', self.host), ('端口', self.port), ('六位房间码', self.code)]:
                    self.label(box, label, 11, MUTED, PANEL).pack(anchor='w', pady=(6, 4))
                    ttk.Entry(box, textvariable=var).pack(fill='x')
                ttk.Button(box, text='加入房间', style='Accent.TButton', command=self.join).pack(fill='x', pady=20)
        self.label(self.shell, '无需公网服务器。房主退出后房间结束；朋友的电脑也需要解压运行本程序。',
                   11, MUTED).pack(anchor='w', pady=8)
        self.label(self.shell, textvariable=self.status, color=GOLD, anchor='w').pack(fill='x', pady=8)

    def _valid(self):
        if not self.name.get().strip() or len(self.name.get().strip()) > 16:
            raise ValueError('请输入 1～16 个字符的昵称。')
        port = int(self.port.get())
        if not 1024 <= port <= 65535:
            raise ValueError('端口应为 1024～65535。')
        return port

    def create(self, practice=False):
        try:
            port = self._valid()
            self.room = Room(('127.0.0.1', 0) if practice else ('0.0.0.0', port))
            self.room.launch()
        except (OSError, ValueError) as exc:
            self.status.set(f'无法创建房间：{exc}。如端口占用，可修改右侧端口。')
            return
        port = self.room.server_address[1]
        self.practice_target = int(self.bots.get()) + 1 if practice else None
        try:
            addresses = sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                                if not x[4][0].startswith('127.')})
        except OSError:
            addresses = []
        address = ' / '.join(addresses) or '请在系统网络设置查看本机 IPv4 地址'
        self.connection_label.set('本机练习' if practice else f'房主地址：{address}    端口：{port}    房间码：{self.room.code}')
        self._connect('127.0.0.1', port, self.room.code, self.room.owner)

    def join(self):
        try:
            port = self._valid()
            if not self.host.get().strip():
                raise ValueError('请输入房主地址。')
            code = self.code.get().strip()
            if len(code) != 6 or not code.isdigit():
                raise ValueError('房间码应为六位数字。')
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.connection_label.set(f'已选择房间：{self.host.get().strip()}:{port}')
        self._connect(self.host.get().strip(), port, code)

    def _connect(self, host, port, code, owner=None):
        self.client = Client()
        self.connection = (host, port, self.name.get().strip(), code, owner)
        self.client.connect(*self.connection)
        self.status.set('正在连接……')
        self._table_shell()

    def _table_shell(self):
        for child in self.shell.winfo_children():
            child.destroy()
        # 中央桌面和手牌区共同承担缩放，底部仅保留说明与状态文本。
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(4, weight=1)
        self.shell.rowconfigure(6, weight=1)
        top = tk.Frame(self.shell, bg=BG)
        top.grid(row=0, column=0, sticky='ew')
        self.label(top, 'UNO NO MERCY', 23).pack(side='left')
        for text, command in [('返回大厅', self.leave), ('玩法', self.help), ('重连', self.reconnect), ('记录', self.toggle_log)]:
            ttk.Button(top, text=text, command=command).pack(side='right', padx=4)
        self.label(self.shell, textvariable=self.connection_label, size=10, color=MUTED, anchor='w').grid(row=1, column=0, sticky='ew', pady=6)
        self.players_frame = tk.Frame(self.shell, bg=BG)
        self.players_frame.grid(row=2, column=0, sticky='ew', pady=8)
        self.controls = tk.Frame(self.shell, bg=BG)
        self.controls.grid(row=3, column=0, sticky='ew', pady=4)
        self.start_btn = ttk.Button(self.controls, text='开始游戏', style='Accent.TButton', command=self.start_round)
        self.start_btn.pack(side='left', padx=(0, 8))
        self.add_btn = ttk.Button(self.controls, text='添加电脑', command=lambda: self.send('add_bot'))
        self.add_btn.pack(side='left', padx=4)
        self.remove_btn = ttk.Button(self.controls, text='移除末尾电脑', command=lambda: self.send('remove_bot'))
        self.remove_btn.pack(side='left', padx=4)
        self.label(self.controls, '剩余人数结束：', size=10).pack(side='left', padx=(8, 0))
        self.end_box = ttk.Combobox(self.controls, values=('1',), textvariable=self.end_remaining,
                                   width=3, state='readonly')
        self.end_box.pack(side='left', padx=3)
        self.turn_label = self.label(self.controls, color=GOLD)
        self.turn_label.pack(side='right')
        self.turn_label.bind('<Button-1>', lambda _: self.show_podium(self.state['game']['round_id'])
                             if self.state and self.state['game'] and self.state['game']['winner'] is not None else None)
        middle = tk.Frame(self.shell, bg=BG)
        middle.grid(row=4, column=0, sticky='nsew', pady=8)
        self.table = tk.Canvas(middle, height=300, bg=TABLE, highlightthickness=0)
        self.table.pack(side='left', fill='both', expand=True)
        self.table.bind('<Configure>', lambda _: self._draw_table())
        self.table.bind('<Button-1>',self._table_click)
        self.table.bind('<Button-3>',self._admin_menu)
        sidebar = tk.Frame(middle, bg=PANEL, width=270)
        self.log_panel = sidebar
        self.label(sidebar, '牌局记录', 12, GOLD, PANEL).pack(anchor='w', padx=12, pady=8)
        self.log = tk.Text(sidebar, width=29, height=10, bg=PANEL, fg=MUTED,
                           font=('Microsoft YaHei UI', 10), relief='flat', wrap='word', state='disabled')
        logscroll = ttk.Scrollbar(sidebar, command=self.log.yview)
        logscroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=logscroll.set)
        self.log.pack(fill='both', expand=True, padx=(10, 0), pady=(0, 10))
        handtop = tk.Frame(self.shell, bg=BG)
        handtop.grid(row=5, column=0, sticky='ew', pady=5)
        self.hand_label = self.label(handtop, '你的手牌', 13)
        self.hand_label.pack(side='left')
        ttk.Checkbutton(handtop, text='可出牌排前面', variable=self.legal_first,
                        command=self._draw_hand).pack(side='right')
        self.label(handtop, '亮框可出 · 悬停放大 · 7 拖向头像换牌', 10, MUTED).pack(side='right', padx=15)
        handbox = tk.Frame(self.shell, bg=BG)
        handbox.grid(row=6, column=0, sticky='nsew')
        self.backpack = tk.Frame(handbox, bg=PANEL, width=100)
        self.backpack.pack(side='right', fill='y', padx=(8,0))
        self.label(self.backpack, '你的背包', 11, GOLD, PANEL).pack(padx=8,pady=20)
        self.uno_btn = tk.Button(self.backpack, text='UNO!', bg='#e72b46', fg='white',
                                 font=('Arial',18,'bold'), command=self.shout, relief='flat', cursor='hand2')
        self.uno_btn.pack(padx=8,pady=8)
        self.label(self.backpack, '随时可喊', 9, MUTED, PANEL).pack()
        ttk.Checkbutton(self.backpack,text='出牌同时\n喊 UNO',variable=self.declare).pack(padx=5,pady=12)
        self.hand_canvas = tk.Canvas(handbox, bg=BG, height=225, highlightthickness=0)
        self.hand_canvas.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(handbox, orient='vertical', command=self.hand_canvas.yview)
        scroll.pack(side='right', fill='y')
        self.hand_canvas.configure(yscrollcommand=scroll.set)
        self.hand_canvas.bind('<Configure>', lambda _: self._draw_hand())
        self.hand_canvas.bind('<B1-Motion>', self._drag_move)
        self.hand_canvas.bind('<Motion>', self._hover)
        self.hand_canvas.bind('<Button-3>',self._admin_menu)
        self.hand_canvas.bind('<Leave>', lambda _: self._unhover())
        self.hand_canvas.bind('<ButtonRelease-1>', self._drag_release)
        self.hand_canvas.bind('<MouseWheel>', lambda e: self.hand_canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        self.hand_canvas.bind('<Button-4>', lambda e: self.hand_canvas.yview_scroll(-1, 'units'))
        self.hand_canvas.bind('<Button-5>', lambda e: self.hand_canvas.yview_scroll(1, 'units'))
        self.description = self.label(self.shell, '等待玩家入座。', 10, MUTED, anchor='w')
        self.description.grid(row=7, column=0, sticky='ew', pady=5)
        self.label(self.shell, textvariable=self.status, size=10, color=GOLD, anchor='w', wraplength=900).grid(row=9, column=0, sticky='ew', pady=5)
        self.render()

    def _space_uno(self,event):
        # 输入昵称、地址或弹窗时保留空格原本的用途，并限制长按自动重复。
        if not self.state or event.widget.winfo_class() in ('Entry','TEntry','Text','TCombobox'):
            return
        if time.monotonic()-self.last_space > .35:
            self.last_space=time.monotonic()
            self.shout()
        return 'break'

    def _shortcut_tags(self,widget):
        # 把快捷键放在按钮默认空格行为之前，避免同时触发“开始”或“抓漏喊”。
        if widget.winfo_class() not in ('Entry','TEntry','Text','TCombobox'):
            tags=widget.bindtags()
            if 'UnoShortcut' not in tags:
                widget.bindtags(('UnoShortcut',)+tags)
        for child in widget.winfo_children():
            self._shortcut_tags(child)

    def _table_click(self,event):
        if not self.state or not self.state['game']:
            return
        g=self.state['game']
        if (g['current']!=self.state['seat'] or g['winner'] is not None or self.state['paused']
                or g['legal'] or g['players'][self.state['seat']]['out']):
            return
        w,h=self.table.winfo_width(),self.table.winfo_height()
        hit=(abs(event.x-w/2)<150 and abs(event.y-h*.5)<70) if g['pending'] else (abs(event.x-w*.84)<65 and abs(event.y-h*.45)<90)
        if hit:
            self.send('draw')

    def _admin_menu(self,event):
        if not self.state or not self.state['game']:
            return
        g=self.state['game']
        p=g['players'][self.state['seat']]
        if not p.get('admin') or p['out'] or g['winner'] is not None:
            return
        menu=tk.Menu(self.root,tearoff=False)
        for kind in ('reverse4','draw6','draw10','roulette'):
            menu.add_command(label='生成 '+LABELS[kind],command=lambda kind=kind:self.send('forge',kind=kind))
        try:
            menu.tk_popup(event.x_root,event.y_root)
        finally:
            menu.grab_release()

    def shout(self):
        if self.client and self.client.connected:
            self.send('shout')
        else:
            self.fx.add({'kind':'uno','seat':0})

    def send(self, op, **kwargs):
        try:
            msg = dict(op=op, **kwargs)
            if self.state and self.state['game']:
                msg.setdefault('revision', self.state['game']['revision'])
            self.client.send(msg)
        except (OSError, AttributeError) as exc:
            self.status.set(str(exc))

    def reconnect(self):
        if not self.client or self.client.connected:
            self.status.set('当前连接仍在线。')
            return
        self.status.set('尝试回到原座位……')
        self.client.connect(*self.connection)

    def _poll(self):
        if self.client:
            try:
                while True:
                    msg = self.client.events.get_nowait()
                    if msg['type'] == 'state':
                        self.state = msg
                        self.status.set('玩家离线，已暂停；可等待重连或让电脑接管。' if msg['paused'] else '已连接。')
                        self.render()
                        if self.practice_target and not msg['game']:
                            if len(msg['members']) < self.practice_target:
                                self.root.after(100, lambda: self.send('add_bot'))
                            else:
                                self.practice_target = None
                                self.status.set('电脑已入座。请设置结束人数，再点击开始游戏。')
                    elif msg['type'] == 'shout':
                        self.fx.add({'kind':'uno','seat':msg['seat']})
                    elif msg['type'] in ('error', 'closed'):
                        self.status.set(msg['message'])
                    elif msg['type'] == 'disconnected':
                        self.status.set(self.status.get() + ' 连接已断开，可点击重连或返回大厅。')
                        self.render()
            except queue.Empty:
                pass
        self.root.after(80, self._poll)

    def render(self):
        s = self.state
        connected = bool(self.client and self.client.connected)
        g = s['game'] if s else None
        host = bool(s and s['host'] and connected)
        def enabled(button, yes):
            button.configure(state='normal' if yes else 'disabled')
        for button in (self.add_btn, self.remove_btn):
            enabled(button, host and g is None)
        enabled(self.start_btn, host and (g is None or g['winner'] is not None))
        self.end_box.configure(values=tuple(str(i) for i in range(1, max(2, len(s['members']) if s else 2))),
                               state='readonly' if host and (g is None or g['winner'] is not None) else 'disabled')
        if s and int(self.end_remaining.get()) >= len(s['members']):
            self.end_remaining.set(str(max(1, len(s['members'])-1)))
        self.start_btn.configure(text='再来一局' if g else '开始游戏')
        for child in self.players_frame.winfo_children():
            child.destroy()
        self.avatar_widgets = {}
        if g:
            theme = tint(seat_color(s,g['current']), .24)
            self.root.configure(bg=theme)
            self.shell.configure(bg=theme)
            self.players_frame.configure(bg=theme)
        if s:
            for i, member in enumerate(s['members']):
                current = g and g['current'] == i and g['winner'] is None
                box = tk.Frame(self.players_frame, bg=PANEL, highlightthickness=2,
                               highlightbackground=seat_color(s,i) if current else PANEL)
                box.pack(side='left', fill='x', expand=True, padx=3)
                suffix = '（你）' if i == s['seat'] else '（电脑）' if member['bot'] else ''
                avatar = tk.Canvas(box, width=80, height=76, bg=PANEL, highlightthickness=0)
                self.avatar_widgets[i] = avatar
                avatar.pack(pady=(4, 0))
                retired = bool(g and g['players'][i]['out'])
                finished = bool(g and g['players'][i]['finished'])
                if member['name'].strip().casefold() in ('admin','op'):
                    for r,col in ((37,'#6a5024'),(34,'#b88b31'),(31,'#ffeaa1')):
                        avatar.create_oval(40-r,38-r,40+r,38+r,outline=col,width=3)
                radius = 33 if current else 22
                avatar.create_oval(40-radius,38-radius,40+radius,38+radius,
                                   fill=tint(seat_color(s,i), .3 if retired else .6),
                                   outline=seat_color(s,i), width=4 if current else 2)
                avatar.create_text(40,38,text=member['name'][:1],fill=TEXT,font=('Microsoft YaHei UI',24 if current else 15,'bold'))
                if retired:
                    badge = '胜' if finished else '亡'
                    avatar.create_oval(52, 48, 74, 70, fill='#b88627' if finished else '#a23749', outline='white')
                    avatar.create_text(63,59,text=badge,fill='white',font=('Microsoft YaHei UI',9,'bold'))
                    if not finished:
                        avatar.create_line(24,22,56,54,fill='#e55b64',width=3)
                self.label(box, member['name'] + suffix, 10, GOLD if current else TEXT, PANEL).pack(pady=(5, 2))
                info = '已入座' if not g else '已获胜退场' if g['players'][i]['finished'] else '爆炸死亡' if g['players'][i]['out'] else f"{g['players'][i]['count']} / 36 张"
                if not member['connected']:
                    info += ' · 离线'
                self.label(box, info + f" · 累计 {member['total']}", 9, MUTED, PANEL).pack(pady=(0, 5))
                if host and not member['connected']:
                    ttk.Button(box, text='电脑接管', command=lambda i=i: self.takeover(i)).pack(pady=3)
                elif g and i in g['uno_open'] and i != s['seat'] and not g['players'][s['seat']]['out']:
                    ttk.Button(box, text='抓漏喊', command=lambda i=i: self.send('catch', target=i)).pack(pady=3)
        active = bool(g and connected and not s['paused'] and g['winner'] is None and not g['players'][s['seat']]['out'])
        turn = active and g['current'] == s['seat']
        enabled(self.uno_btn, True)
        if g:
            who = g['players'][g['current']]['name']
            text = f'轮到 {who}' if g['winner'] is None else '对局结束 · 领奖台'
            self.turn_label.configure(text='对局暂停' if s['paused'] else text)
            self.hand_label.configure(text=f"你的手牌：{len(g['hand'])} 张 · 可出 {len(g['legal'])} 张")
            self.log.configure(state='normal')
            self.log.delete('1.0', 'end')
            self.log.insert('end', '\n\n'.join(g['log']))
            self.log.see('end')
            self.log.configure(state='disabled')
            if self.selected not in [c['uid'] for c in g['hand']]:
                self.selected = None
            if s['paused']:
                self.description.configure(text='等待离线玩家重连，或由房主选择电脑接管。')
            elif g['players'][s['seat']]['out']:
                self.description.configure(text='你已清牌获胜退场，可以继续观战。' if g['players'][s['seat']]['finished'] else '你已达到 36 张爆炸死亡，可以继续观战。')
            elif g['forced'] is not None and turn:
                self.description.configure(text='已抽到可用牌，请打出金框标记的这张牌。')
            elif g['roulette']:
                self.description.configure(text=f'颜色轮盘：等待 {who} 选择目标颜色。')
            elif self.selected is None:
                self.description.configure(text='悬停放大并查看说明；拖到中央出牌堆出牌，7 可拖向对手头像换牌。')
        if g:
            self._track_visuals(g)
            self.fx.consume(g)
        self._shortcut_tags(self.shell)
        self._draw_table()
        self._draw_hand()

    def _card(self, canvas, x, y, w, h, card, legal=False, selected=False, tag=None, dim=False):
        if self.state and self.state['game'] and self.state['game']['players'][self.state['seat']].get('admin'):
            card=dict(card,gold=True)
        paint_card(canvas, x+w/2, y+h/2, w, h, card, tags=(tag,) if tag else (),
                   selected=selected, legal=legal, dim=dim)

    def _draw_table(self):
        if not hasattr(self, 'table') or not self.table.winfo_exists():
            return
        draw_scene(self)

    def _draw_hand(self):
        if not hasattr(self, 'hand_canvas') or not self.hand_canvas.winfo_exists():
            return
        canvas = self.hand_canvas
        canvas.delete('all')
        g = self.state['game'] if self.state else None
        if not g:
            return
        me=g['players'][self.state['seat']]
        if me['out']:
            canvas.configure(scrollregion=(0,0,canvas.winfo_width(),canvas.winfo_height()))
            canvas.yview_moveto(0)
            canvas.create_text(canvas.winfo_width()/2,85,text='你已清牌获胜' if me['finished'] else '你已爆炸！',
                               fill=GOLD if me['finished'] else '#ff5d67',font=('Microsoft YaHei UI',38,'bold'))
            canvas.create_text(canvas.winfo_width()/2,145,text='已退场 · 可以继续观战，也可以按空格喊 UNO',fill=MUTED,font=('Microsoft YaHei UI',12))
            self.hand_hits=[]
            return
        cards = list(g['hand'])
        self.hand_hits = []
        if self.legal_first.get():
            cards.sort(key=lambda c: c['uid'] not in g['legal'])
        columns = max(1, (canvas.winfo_width()-24)//102)
        indexed = list(enumerate(cards))
        indexed.sort(key=lambda item:(item[1]['uid']==self.hover_uid, item[1]['uid']==self.selected))
        for i, card in indexed:
            x, y = 22+(i % columns)*102, 48+(i//columns)*210
            uid = card['uid']
            tag = f'card{uid}'
            legal = uid in g['legal']
            chosen = uid == self.selected
            hover = uid == self.hover_uid
            self.hand_hits.append((uid,x,y,x+86,y+121))
            self._card(canvas, x-21 if hover else x-7 if chosen else x, y-42 if hover else y-17 if chosen else y,
                       128 if hover else 102 if chosen else 86, 180 if hover else 143 if chosen else 121,
                       card, legal, chosen or hover, tag, dim=not legal)
            if chosen:
                canvas.create_text(x+43,y+139,text=LABELS.get(card['kind'], '换牌' if card['kind']=='7' else '交牌' if card['kind']=='0' else '数字牌'),
                                   fill=GOLD,font=('Microsoft YaHei UI',10))
            canvas.tag_bind(tag, '<Button-1>', lambda e, uid=uid: self._drag_start(e,uid))
            canvas.tag_bind(tag, '<Double-Button-1>', lambda _, uid=uid: self.quick_play(uid))
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(210, ((len(cards)+columns-1)//columns)*210+25)))
        if self.hover_uid is not None or self.selected is not None:
            selected_card = next((c for c in cards if c['uid']==(self.hover_uid if self.hover_uid is not None else self.selected)),None)
            if selected_card:
                self.description.configure(text=selected_card['label']+'：'+DESCRIPTIONS.get(selected_card['kind'],'匹配当前颜色或数字即可出牌。'))

    def _hover(self, event):
        if self.drag_active:
            return
        x,y = self.hand_canvas.canvasx(event.x),self.hand_canvas.canvasy(event.y)
        uid = next((uid for uid,x0,y0,x1,y1 in self.hand_hits if x0<=x<=x1 and y0<=y<=y1),None)
        if uid != self.hover_uid:
            self.hover_uid = uid
            self._draw_hand()

    def _unhover(self):
        self.hover_uid = None
        self._draw_hand()

    def select(self, uid):
        if not self.state or not self.state['game'] or not any(c['uid']==uid for c in self.state['game']['hand']):
            return
        self.selected = uid
        g = self.state['game']
        card = next(c for c in g['hand'] if c['uid'] == uid)
        desc = DESCRIPTIONS.get(card['kind'], '匹配当前颜色或数字即可出牌。')
        self.description.configure(text=card['label'] + '：' + desc)
        valid = uid in g['legal'] and not self.state['paused'] and self.client.connected
        self._draw_hand()
        bounds=self.hand_canvas.bbox(f'card{uid}')
        if bounds:
            top=self.hand_canvas.canvasy(0)
            if bounds[1]<top or bounds[3]>top+self.hand_canvas.winfo_height():
                region=self.root.tk.splitlist(self.hand_canvas.cget('scrollregion'))
                total=float(region[3]) if region else 1
                self.hand_canvas.yview_moveto(max(0,bounds[1]-5)/max(1,total))

    def quick_play(self, uid):
        self.select(uid)
        self.play()

    def toggle_log(self):
        if not hasattr(self,'log_panel') or not self.log_panel.winfo_exists():
            return
        if self.log_panel.winfo_manager():
            self.log_panel.pack_forget()
        else:
            self.log_panel.pack(side='right',fill='y',padx=(12,0))

    def _auto_play_drawn(self, key):
        # 动画期间可能断线、重开或已经手动出牌；旧回调不能误打新牌。
        if not self.state or not self.state['game']:
            return
        g=self.state['game']
        if (g['round_id'],g['forced'])!=key or self.state['paused'] or not self.client.connected:
            return
        if g['current']!=self.state['seat'] or g['winner'] is not None:
            return
        self.select(g['forced'])
        self.play()

    def _drag_start(self, event, uid):
        self._clear_drag()
        self.select(uid)
        self.drag_uid=uid
        self.drag_origin=(event.x_root,event.y_root)
        self.drag_round=self.state['game']['round_id']

    def _drag_move(self,event):
        if self.drag_uid is None or not self.state or not self.state['game']:
            return
        g=self.state['game']
        card=next((c for c in g['hand'] if c['uid']==self.drag_uid),None)
        if card is None or g['round_id']!=self.drag_round:
            self._clear_drag()
            return
        if not self.drag_active and abs(event.x_root-self.drag_origin[0])+abs(event.y_root-self.drag_origin[1])<8:
            return
        self.drag_active=True
        if card['kind']=='7' and self.drag_uid in g['legal'] and len(g['hand'])>1:
            self.fx.arrow = (self.drag_origin,(event.x_root,event.y_root))
            return
        if self.drag_ghost is None:
            self.drag_ghost=tk.Canvas(self.root,width=112,height=159,bg=BG,highlightthickness=0)
            self._card(self.drag_ghost,5,5,102,143,card,legal=self.drag_uid in g['legal'],selected=True)
        self.drag_ghost.place(x=event.x_root-self.root.winfo_rootx()-56,
                              y=event.y_root-self.root.winfo_rooty()-70)
        self.root.tk.call('raise',self.drag_ghost._w)
        self.drag_over=pile_hit(event.x_root-self.table.winfo_rootx(),event.y_root-self.table.winfo_rooty(),
                               self.table.winfo_width(),self.table.winfo_height())

    def _drag_release(self,event):
        uid,active=self.drag_uid,self.drag_active
        target = self._avatar_target(event.x_root,event.y_root)
        round_id=getattr(self,'drag_round',None)
        inside=pile_hit(event.x_root-self.table.winfo_rootx(),event.y_root-self.table.winfo_rooty(),
                        self.table.winfo_width(),self.table.winfo_height())
        self._clear_drag()
        if not active or uid is None:
            return
        g=self.state['game'] if self.state else None
        if not g or g['round_id']!=round_id:
            return
        card = next((c for c in g['hand'] if c['uid']==uid),None)
        if (target is not None and card and card['kind']=='7' and len(g['hand'])>1
                and uid in g['legal'] and not self.state['paused']):
            self.send('play',card=uid,target=target,declare=self.declare.get())
            self.declare.set(False)
            return
        if inside and uid in g['legal'] and not self.state['paused']:
            self.select(uid)
            self.play()
        else:
            self.status.set('拖拽取消：请将当前可出的牌放到中央出牌堆。')
        self._draw_table()

    def _avatar_target(self, x, y):
        if not self.state or not self.state['game']:
            return None
        for seat,widget in self.avatar_widgets.items():
            if seat == self.state['seat'] or self.state['game']['players'][seat]['out']:
                continue
            if (widget.winfo_rootx() <= x <= widget.winfo_rootx()+widget.winfo_width()
                    and widget.winfo_rooty() <= y <= widget.winfo_rooty()+widget.winfo_height()):
                return seat
        return None

    def _clear_drag(self):
        self.fx.arrow = None
        if self.drag_ghost and self.drag_ghost.winfo_exists():
            self.drag_ghost.destroy()
        self.drag_ghost=None
        self.drag_uid=None
        self.drag_active=False
        self.drag_over=False

    def choose(self, title, options, callback):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        win = tk.Toplevel(self.root)
        self.dialog = win
        win.title(title)
        win.configure(bg=BG)
        win.transient(self.root)
        win.resizable(False, False)
        self.label(win, title, 16).pack(padx=30, pady=20)
        def finish(value):
            win.destroy()
            self.dialog = None
            callback(value)
        for text, value in options:
            ttk.Button(win, text=text, command=lambda v=value: finish(v)).pack(fill='x', padx=25, pady=5)
        ttk.Button(win, text='取消', command=win.destroy).pack(fill='x', padx=25, pady=20)
        win.grab_set()

    def play(self):
        if not self.state or not self.state['game']:
            return
        g = self.state['game']
        if self.selected not in g['legal'] or self.state['paused']:
            self.status.set('请选择一张金色框标记的可出牌。')
            return
        c = next(c for c in g['hand'] if c['uid'] == self.selected)
        action = dict(card=c['uid'], revision=g['revision'], declare=self.declare.get())
        def submit(**extra):
            self.send('play', **action, **extra)
            self.declare.set(False)
        if c['color'] == 'wild':
            open_wheel(self,lambda color: submit(color=color))
        elif c['kind'] == '7' and len(g['hand']) > 1:
            self.choose('选择换牌对象', [(f"{p['name']} · {p['count']} 张", i)
                        for i, p in enumerate(g['players']) if i != self.state['seat'] and not p['out']],
                        lambda target: submit(target=target))
        else:
            submit()

    def roulette(self):
        if not self.state or not self.state['game']:
            return
        revision = self.state['game']['revision']
        self.choose('选择你要抽中的颜色', [(COLOR_NAMES[x], x) for x in COLORS],
                    lambda color: self.send('color', color=color, revision=revision))

    def takeover(self, seat):
        if messagebox.askyesno('电脑接管', '接管后，该朋友无法重新加入这个座位。继续？'):
            self.send('takeover', target=seat)

    def help(self):
        win = tk.Toplevel(self.root)
        win.title('玩法说明')
        win.geometry('760x650')
        text = tk.Text(win, bg=BG, fg=TEXT, padx=22, pady=20, wrap='word',
                       font=('Microsoft YaHei UI', 11))
        scroll = ttk.Scrollbar(win, command=text.yview)
        scroll.pack(side='right', fill='y')
        text.configure(yscrollcommand=scroll.set)
        text.pack(fill='both', expand=True)
        text.insert('1.0', HELP)
        text.configure(state='disabled')

    def _disconnect(self):
        self._clear_drag()
        if self.client:
            self.client.close()
        self.client = None
        if self.room:
            room = self.room
            self.room = None
            threading.Thread(target=room.close, daemon=True).start()
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.destroy()
        self.state = None
        self.selected = None
        self.practice_target = None
        if self.podium and self.podium.winfo_exists():
            self.podium.destroy()

    def start_round(self):
        self.send('start', end_remaining=int(self.end_remaining.get()))

    def _track_visuals(self, g):
        """只对新事件启动一次动画；重复快照与逐帧重绘不重复触发。"""
        if self.visual_round != g['round_id']:
            self.visual_round = g['round_id']
            self.visual_last = None
            self.visual_deaths = []
            self.seen_draw = None
            self.auto_forced = None
            self.death_names = []
            if self.podium and self.podium.winfo_exists():
                self.podium.destroy()
        recent = tuple(c['uid'] for c in g['recent'])
        if recent != self.visual_last:
            self.effect_since = time.monotonic()
            self.visual_last = recent
        new_dead = [i for i in g['death_order'] if i not in self.visual_deaths]
        if new_dead:
            self.death_since = time.monotonic()
            self.death_names = [g['players'][i]['name'] for i in new_dead]
        self.visual_deaths = list(g['death_order'])
        event = g.get('draw_event')
        if event and self.seen_draw != event['serial']:
            self.seen_draw = event['serial']
            self.draw_since = time.monotonic()
        if g['forced'] is not None and g['current']==self.state['seat'] and not self.state['paused']:
            key=(g['round_id'],g['forced'])
            if self.auto_forced != key:
                self.auto_forced=key
                self.selected=g['forced']
                self.root.after(850,lambda key=key:self._auto_play_drawn(key))
        else:
            self.auto_forced=None
        if g['winner'] is not None and self.podium_round != g['round_id']:
            self.podium_round = g['round_id']
            self.root.after(1800 if new_dead else 600, lambda round_id=g['round_id']: self.show_podium(round_id))

    def _animate(self):
        if self.state and self.state['game']:
            self._draw_table()
        self.fx.tick()
        self.root.after(33, self._animate)

    def show_podium(self, round_id):
        if not self.state or not self.state['game'] or self.state['game']['round_id'] != round_id:
            return
        for started,event in self.fx.active:
            duration=1+event['count']*.10+.85 if event['kind']=='reveal' else 1 if event['kind']=='color' else 0
            if time.monotonic()-started < duration:
                self.root.after(150,lambda:self.show_podium(round_id))
                return
        if self.podium and self.podium.winfo_exists():
            self.podium.lift()
            return
        g = self.state['game']
        win = tk.Toplevel(self.root)
        self.podium = win
        win.title('UNO NO MERCY · 领奖台')
        win.geometry('820x650')
        win.minsize(700, 560)
        win.configure(bg=BG)
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        canvas.bind('<Configure>', lambda _: draw_podium(canvas, g))
        ttk.Button(win, text='返回牌桌', command=win.destroy).pack(pady=14)
        win.after_idle(lambda: draw_podium(canvas, g))

    def leave(self):
        if self.state and not messagebox.askyesno('离开房间',
                '离开会丢失原座位的重连凭据。房主离开将关闭整间房。确定离开？'):
            return
        self._disconnect()
        self.status.set('已返回大厅。')
        self._menu()

    def close(self):
        if self.state and not messagebox.askyesno('退出', '确认退出？房主退出会结束房间。'):
            return
        self._disconnect()
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit('无法打开图形界面。请在有桌面的电脑上运行，并确认已安装 Tk。\n' + str(exc))
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
