"""公开事件驱动的视觉层；仅传座位/张数，绝不传其他人的牌面。

Windows 使用透明、鼠标穿透窗口跨越 Tk 子控件绘制。其他系统降级为
牌桌内特效。动画不阻塞主循环，不改变服务器回合或电脑计时。
"""
import math
import sys
import time
import tkinter as tk
from color_wheel import INK, NAMES
from card_art import paint_card

PLAYER_COLORS = ('#65a8ff', '#f875a5', '#51d6ae', '#f0c45e', '#b58aff', '#ff985f')

def seat_color(state,seat):
    game=state.get('game') if state else None
    people=game['players'] if game else state.get('members',[]) if state else []
    admin=seat<len(people) and (people[seat].get('admin') or people[seat]['name'].strip().casefold() in ('admin','op'))
    return '#ffda69' if admin else PLAYER_COLORS[seat]


def tint(color, strength=.22):
    return '#' + ''.join(f'{int(int(color[i:i+2],16)*strength):02x}' for i in (1,3,5))


class Effects:
    def __init__(self, app):
        self.app = app
        self.round = None
        self.last = 0
        self.active = []
        self.arrow = None
        self.window = None
        if sys.platform == 'win32':
            # 透明背景 + WS_EX_TRANSPARENT，让拖拽和按钮继续收到鼠标事件。
            import ctypes
            win = tk.Toplevel(app.root)
            win.withdraw()
            win.overrideredirect(True)
            win.transient(app.root)
            win.configure(bg='#010203')
            win.attributes('-transparentcolor', '#010203')
            canvas = tk.Canvas(win, bg='#010203', highlightthickness=0)
            canvas.pack(fill='both', expand=True)
            win.update_idletasks()
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            hwnd = user32.GetParent(win.winfo_id())
            user32.SetWindowLongW(hwnd, -20, user32.GetWindowLongW(hwnd, -20) | 0x20 | 0x08000000)
            self.window, self.canvas = win, canvas

    def consume(self, game):
        events = game.get('effects', [])
        if self.round != game['round_id']:
            self.round = game['round_id']
            self.active.clear()
            self.last = 0 if game['revision'] == 0 else max((e['id'] for e in events), default=0)
        for event in events:
            if event['id'] > self.last:
                self.add(event)
                self.last = event['id']

    def add(self, event):
        self.active.append((time.monotonic(), event))
        self.active = self.active[-48:]

    def point(self, widget, fx=.5, fy=.5):
        base = self.app.root if self.window else self.app.table
        x = widget.winfo_rootx()-base.winfo_rootx()+widget.winfo_width()*fx
        y = widget.winfo_rooty()-base.winfo_rooty()+widget.winfo_height()*fy
        if not self.window:
            x = min(max(20,x),base.winfo_width()-20)
            y = min(max(20,y),base.winfo_height()-20)
        return x,y

    def seat_point(self, seat):
        app = self.app
        widget = app.backpack if app.state and seat == app.state['seat'] else app.avatar_widgets.get(seat,app.table)
        return self.point(widget)

    def tick(self):
        app = self.app
        if not hasattr(app,'table') or not app.table.winfo_exists():
            self.active.clear()
            if self.window: self.window.withdraw()
            return
        now = time.monotonic()
        self.active = [(t,e) for t,e in self.active if now-t < (1+e['count']*.10+.85 if e['kind']=='reveal' else 2.5)]
        c = self.canvas if self.window else app.table
        c.delete('fx')
        if self.window:
            if not self.active and not self.arrow or not app.root.winfo_viewable():
                self.window.withdraw()
                return
            self.window.geometry(f'{app.root.winfo_width()}x{app.root.winfo_height()}+{app.root.winfo_rootx()}+{app.root.winfo_rooty()}')
            self.window.deiconify()
            self.window.lift()
        width = app.root.winfo_width() if self.window else c.winfo_width()
        height = app.root.winfo_height() if self.window else c.winfo_height()
        for start,event in self.active:
            elapsed = now-start
            kind = event['kind']
            if kind == 'color' and elapsed < 1:
                x,y=width/2,height*.45
                radius=72+16*math.sin(elapsed*math.pi)
                c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=INK[event['color']],outline='white',width=5,tags='fx')
                name=app.state['game']['players'][event['seat']]['name']
                c.create_text(x,y-12,text=NAMES[event['color']],fill='#101827',font=('Microsoft YaHei UI',28,'bold'),tags='fx')
                c.create_text(x,y+30,text=name+' 选择',fill='#101827',font=('Microsoft YaHei UI',12),tags='fx')
            if kind == 'reveal' and elapsed >= 1:
                cards=event['cards']
                shown=min(len(cards),int((elapsed-1)/.10)+1)
                ox,oy=self.point(app.table,.15,.46)
                collecting=elapsed-1-len(cards)*.10
                # 展示时左侧保留卡片缩略图，最新一张较大；收牌时整批同时飞行。
                for j,card in enumerate(cards[:shown]):
                    x=ox-65+(j%6)*24
                    y=oy-50+(j//6)*22
                    w,h=(83,118) if j==shown-1 and collecting<0 else (30,43)
                    if collecting>=0:
                        dest=self.point(app.avatar_widgets.get(event['seat'],app.table))
                        t=min(1,collecting/.75)
                        dx,dy=dest[0]-x,dest[1]-y
                        x,y=x+dx*t,y+dy*t-35*math.sin(t*math.pi)
                        c.create_line(x-dx*.07,y-dy*.07,x,y,fill=seat_color(app.state,event['seat']),width=4,tags='fx')
                    paint_card(c,x,y,w,h,card,small=w<40,tags=('fx',))
                c.create_text(ox,oy+108,text=f'轮盘明牌 {shown} / {len(cards)}',fill='white',font=('Microsoft YaHei UI',11,'bold'),tags='fx')
            if kind == 'uno' and elapsed < .95:
                # 冲击线、白描边、红字：先从大字缩到中心，再停留片刻。
                cx,cy = width*.5,height*.45
                for j in range(18):
                    a = j*math.tau/18
                    c.create_line(cx+math.cos(a)*155,cy+math.sin(a)*70,cx+math.cos(a)*width,cy+math.sin(a)*height,fill='#ef344d',width=4,tags='fx')
                size = int(min(135,width*.14)*(1+max(0,1-elapsed/.18)*.55))
                for dx,dy in ((-5,0),(5,0),(0,-5),(0,5)):
                    c.create_text(cx+dx,cy+dy,text='UNO!',fill='white',font=('Arial',size,'bold italic'),tags='fx')
                c.create_text(cx,cy,text='UNO!',fill='#f0203c',font=('Arial',size,'bold italic'),tags='fx')
            moves = []
            if kind == 'draw':
                moves = [(self.point(app.table,.84,.45),self.seat_point(event['seat']),event['count'],event['seat'])]
            elif kind in ('swap','pass'):
                moves = [(self.seat_point(a),self.seat_point(b),count,a) for a,b,count in event['moves']]
                if elapsed < 1.8:
                    c.create_text(width/2,height*.31,text='交换手牌 ⇄' if kind=='swap' else '全员传牌 →',fill=seat_color(app.state,event['seat']),font=('Microsoft YaHei UI',25,'bold'),tags='fx')
            for origin,dest,count,seat in moves:
                for j in range(min(count,36)):
                    p = (elapsed-j*.025)/.65
                    if not 0 <= p <= 1: continue
                    def path(q):
                        return (origin[0]+(dest[0]-origin[0])*q+math.sin(q*math.pi)*35,
                                origin[1]+(dest[1]-origin[1])*q-math.sin(q*math.pi)*65)
                    color = seat_color(app.state,seat)
                    for k in range(5,0,-1):
                        a,b = path(max(0,p-k*.025)),path(max(0,p-(k-1)*.025))
                        c.create_line(*a,*b,fill=tint(color,1-k*.12),width=8-k,tags='fx')
                    x,y = path(p)
                    c.create_polygon(x-9,y-14,x+8,y-11,x+10,y+14,x-7,y+11,fill='#172438',outline=color,width=2,tags='fx')
                    c.create_text(x,y,text='U',fill='white',font=('Arial',9,'bold'),tags='fx')
        if self.arrow:
            origin,end = self.arrow
            base = app.root if self.window else app.table
            ox,oy = base.winfo_rootx(),base.winfo_rooty()
            c.create_line(origin[0]-ox,origin[1]-oy,end[0]-ox,end[1]-oy,fill=seat_color(app.state,app.state['seat']),width=10,arrow='last',arrowshape=(28,34,13),tags='fx')
            for seat,widget in app.avatar_widgets.items():
                if seat != app.state['seat'] and not app.state['game']['players'][seat]['out']:
                    x,y = self.point(widget)
                    c.create_oval(x-35,y-35,x+35,y+35,outline=seat_color(app.state,seat),width=4,tags='fx')
