"""纯 Canvas 原创牌桌特效。角度由牌编号确定，重绘时不会无故抖动。

无需图片库：牌框用旋转多边形，文字使用 Tk 8.6 的 angle 参数。
全部动画运行于主线程 after 回调，不阻塞服务器与其他玩家操作。
"""
import math
import time
from engine import DRAW, COLOR_NAMES, LABELS
from card_art import paint_card

PALETTE = {'red': '#c73f50', 'yellow': '#e6b842', 'green': '#258568',
           'blue': '#356ac0', 'wild': '#30324a'}
GOLD = '#ffd36a'
TEXT = '#edf3f9'


def tilted(canvas, cx, cy, width, height, card, angle, small=False):
    paint_card(canvas,cx,cy,width,height,card,angle=angle,small=small)


def draw_scene(app):
    c=app.table
    c.delete('all')
    w,h=c.winfo_width(),c.winfo_height()
    if w<10 or h<10:
        return
    from effects import PLAYER_COLORS, tint, seat_color
    game = app.state['game'] if app.state else None
    theme = seat_color(app.state,game['current']) if game else '#65a8ff'
    # 当前座位的固定角色色染亮整张牌桌。
    for row in range(16):
        shade=20+row
        color=tint(theme,.20+row*.006)
        c.create_rectangle(0,h*row/16,w,h*(row+1)/16+1,fill=color,outline='')
    c.create_rectangle(5,5,w-5,h-5,outline='#3c6270',width=2)
    c.create_oval(w*.31,h*.09,w*.69,h*.94,outline='#315866',width=1,dash=(3,7))
    g=app.state['game'] if app.state else None
    if not g:
        c.create_text(w/2,h/2-10,text='准备好了吗？',fill=TEXT,font=('Microsoft YaHei UI',25,'bold'))
        c.create_text(w/2,h/2+30,text='设置结束人数，邀请朋友入座',fill=GOLD,font=('Microsoft YaHei UI',12))
        return
    now=time.monotonic()
    cx,cy=w/2,h*.51
    scale=min(1.12,max(.45,h/285))
    chain=g['draw_chain']
    c.create_text(cx,19,text=f"当前：{COLOR_NAMES[g['color']]}色   {'顺时针 →' if g['direction']==1 else '← 逆时针'}",
                  fill=TEXT,font=('Microsoft YaHei UI',11))
    progress=min(1.,(now-app.effect_since)/.42)
    recent=g['recent'] or [g['top']]
    for index,card in enumerate(recent):
        # 最新一张在中心，旧牌向两边自然错位。
        offset=index-(len(recent)-1)
        x=cx+offset*12*scale
        y=cy+(abs(offset)%3-1)*5*scale
        angle=((card['uid']*17+index*7)%19)-9
        if index==len(recent)-1:
            y+=(1-progress)**2*85
        tilted(c,x,y,124*scale,184*scale,card,angle)
    c.create_text(cx,h-17,text='将手牌拖到这里出牌',fill='#b6cecc',font=('Microsoft YaHei UI',10))
    if getattr(app,'drag_active',False):
        valid=getattr(app,'drag_over',False)
        c.create_oval(cx-95*scale,cy-111*scale,cx+95*scale,cy+111*scale,
                      outline=GOLD if valid else '#95c6bf',width=3,dash=(7,5))
    # 左侧罚牌链，四个固定行；所有链中卡片均绘制，长链以重叠节省空间。
    x0,x1=18,w*.285
    n=len(chain)
    level=min(4,n//2)
    pulse=(math.sin(now*(3+level))+1)/2
    accent='#ffdf75' if n<4 else '#ffa143' if n<8 else '#ff5d4e'
    if n >= 2:
        c.create_rectangle(x0,34,x1,h-20,fill='#111e30',outline=accent if n else '#365366',width=1+level*pulse)
        c.create_text((x0+x1)/2,43,text='累计罚抽',fill=accent,font=('Microsoft YaHei UI',10,'bold'))
        c.create_text((x0+x1)/2,74,text=f"+{g['pending']}",fill=accent,
                      font=('Microsoft YaHei UI',34,'bold'))
        row_h=max(19,min(44,(h-126)/4))
        shake=math.sin(now*24)*max(0,level-1)
        for row,value in enumerate((2,4,6,10)):
            cards=[card for card in chain if DRAW.get(card['kind'])==value]
            y=96+row_h*(row+.5)
            c.create_text(x0+24,y,text=f'+{value}',fill=TEXT,font=('Microsoft YaHei UI',10,'bold'))
            available=max(8,x1-x0-110)
            step=min(34,available/max(1,len(cards)-1))
            for j,card in enumerate(cards):
                tilted(c,x0+63+j*step+shake,y,38,row_h*.78,card,((card['uid']*3)%7)-3,small=True)
            c.create_text(x1-12,y,text=f'×{len(cards)}',anchor='e',fill='#a8bace',font=('Microsoft YaHei UI',9))
        if n:
            for j in range(4+level*5):
                t=(now*.5+j*.123)%1
                px=x0+6+(j*71)%max(1,int(x1-x0-14))
                py=h-22-t*max(10,h-62)
                c.create_oval(px-1,py-2,px+1+level*.3,py+2,fill=accent,outline='')
    # 右侧独立抽牌区，正常抽牌动画从这里飞向手牌。
    dx,dy=w*.84,h*.45
    back={'color':'wild','kind':'?'}
    for i in range(3):
        tilted(c,dx-i*4,dy-i*3,79*scale,118*scale,back,0)
    c.create_text(dx,dy+79*scale,text=f"抽牌堆 · {g['deck_count']} 张",fill=TEXT,font=('Microsoft YaHei UI',10))
    c.create_text(dx,h-24,text='36 张爆炸死亡',fill='#e6a58d',font=('Microsoft YaHei UI',10))
    event=g.get('draw_event')
    age_draw=now-getattr(app,'draw_since',0)
    if event and 0<=age_draw<.8:
        name=g['players'][event['seat']]['name']
        c.create_text(cx,max(42,h*.15),text=f"{name} 抽 1 张"+(' · 可出，立即打出' if event['playable'] else ' · 本回合结束'),
                      fill=GOLD,font=('Microsoft YaHei UI',12,'bold'))
    elif g['forced'] is not None:
        c.create_text(dx,dy-82*scale,text='抽到可用牌\n必须立即打出',fill=GOLD,font=('Microsoft YaHei UI',11),justify='center')
    elif g['roulette']:
        c.create_text(dx,dy-82*scale,text='颜色轮盘 · 等待选色',fill=GOLD,font=('Microsoft YaHei UI',10))
    age = now-app.death_since
    if app.death_names and 0 <= age < 1.7:
        # 全桌可见的爆炸：扩散环、火花与死亡名字；不暴露任何私有手牌。
        t = age/1.7
        bx, by = w/2, h/2
        radius = 20+t*min(w,h)*.72
        for k in range(3):
            r = radius*(1-k*.18)
            c.create_oval(bx-r,by-r,bx+r,by+r,outline=('#ff633d','#ffc55b','#fff3ab')[k],width=max(1,8*(1-t)))
        for j in range(36):
            a = j*math.tau/36
            r = radius*(1+(j%4)*.18)
            x,y = bx+math.cos(a)*r,by+math.sin(a)*r
            c.create_line(x,y,x+math.cos(a)*18*(1-t),y+math.sin(a)*18*(1-t),fill='#ffb84d',width=3)
        c.create_rectangle(bx-160,by-34,bx+160,by+34,fill='#421e26',outline='#ff785c',width=2)
        c.create_text(bx,by,text='、'.join(app.death_names)+'\n爆炸死亡 · 36 张',fill='#fff0c6',
                       font=('Microsoft YaHei UI', 17,'bold'),justify='center')
    # 罚牌入口只有受罚者无法继续叠加时出现；普通抽牌直接点右侧牌堆。
    seat=app.state.get('seat',-1)
    actionable=(seat==g['current'] and g['winner'] is None and not app.state.get('paused')
                and not g['players'][seat]['out'] and not g['legal'])
    if actionable and g['pending']:
        c.create_rectangle(w/2-150,h*.5-70,w/2+150,h*.5+70,fill='#4e202b',outline='#ffcf72',width=4)
        c.create_text(w/2,h*.5-24,text=f"接受 +{g['pending']} 张",fill='#ffe193',font=('Microsoft YaHei UI',27,'bold'))
        c.create_text(w/2,h*.5+25,text='无法继续叠加 · 点击这里领取',fill='white',font=('Microsoft YaHei UI',12))
    elif actionable:
        c.create_text(dx,dy+102*scale,text='点击牌堆 · 抽一张',fill=GOLD,font=('Microsoft YaHei UI',12,'bold'))


def draw_podium(c, g):
    c.delete('all')
    w,h = c.winfo_width(),c.winfo_height()
    c.create_text(w/2,35,text='UNO NO MERCY',fill=GOLD,font=('Microsoft YaHei UI',25,'bold'))
    c.create_text(w/2,75,text='领奖台 · 清牌顺序优先，存活者按手牌数排名',fill='#b5c3d4',font=('Microsoft YaHei UI',11))
    ranking = g['ranking']
    base = min(310,h*.54)
    for index in (1,0,2):
        if index >= len(ranking):
            continue
        item = ranking[index]
        x = w/2+(index-1)*190 if index else w/2
        if index==1:
            x=w/2-190
        elif index==2:
            x=w/2+190
        height = (135,95,70)[index]
        color = ('#b78830','#728ba0','#99664e')[index]
        c.create_rectangle(x-80,base-height,x+80,base,fill=color,outline='')
        c.create_text(x,base-height+33,text=f"第 {item['rank']} 名",fill='white',font=('Microsoft YaHei UI',22,'bold'))
        c.create_text(x,base-height-21,text=item['name'],fill=TEXT,font=('Microsoft YaHei UI',14,'bold'))
    labels = {'finished':'清牌获胜','survived':'存活','dead':'爆炸死亡'}
    for i,item in enumerate(ranking):
        y=base+30+i*32
        c.create_text(w*.17,y,text=f"第 {item['rank']} 名",fill=GOLD,anchor='w',font=('Microsoft YaHei UI',11))
        c.create_text(w*.32,y,text=item['name'],fill=TEXT,anchor='w',font=('Microsoft YaHei UI',11))
        c.create_text(w*.64,y,text=f"{labels[item['status']]} · {item['count']} 张",fill='#b5c3d4',anchor='w',font=('Microsoft YaHei UI',11))
