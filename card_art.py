"""原创矢量卡面：圆角纸张、斜椭圆、角标及功能图标，全部随牌旋转。

所有图形共用相同 tag，保证点击、拖拽在文字和图形上都有效。
通过数学坐标变换绘制，支持缩放，不依赖图片包或在线资源。
"""
import math
from engine import COLOR_NAMES, LABELS

PALETTE = {'red':'#ed4d60','yellow':'#f0c64d','green':'#22a382','blue':'#4b84ec','wild':'#20263d'}


def paint_card(c, cx, cy, w, h, card, angle=0, tags=(), selected=False, legal=False, dim=False, small=False):
    theta=math.radians(angle)
    def xy(x,y):
        return (cx+x*w*math.cos(theta)+y*h*math.sin(theta),
                cy-x*w*math.sin(theta)+y*h*math.cos(theta))
    def poly(points, **kwargs):
        c.create_polygon([v for p in points for v in xy(*p)],tags=tags,**kwargs)
    def line(points,**kwargs):
        c.create_line([v for p in points for v in xy(*p)],tags=tags,**kwargs)
    def text(x,y,label,size,color,**kwargs):
        c.create_text(*xy(x,y),text=label,fill=color,angle=angle,tags=tags,
                      font=('Microsoft YaHei UI',max(7,int(size*w)), 'bold'),**kwargs)
    def rounded(left,top,right,bottom,r):
        result=[]
        for x,y,start in ((right-r,top+r,-90),(right-r,bottom-r,0),
                           (left+r,bottom-r,90),(left+r,top+r,180)):
            for j in range(7):
                a=math.radians(start+j*15)
                result.append((x+r*math.cos(a),y+r*math.sin(a)))
        return result
    def ellipse(rx,ry,offset=0):
        # 斜椭圆在卡片局部坐标内，再和整张牌一起旋转。
        return [(rx*math.cos(i*math.tau/64)+offset*math.sin(i*math.tau/64),
                 ry*math.sin(i*math.tau/64)) for i in range(64)]
    outer=rounded(-.5,-.5,.5,.5,.075)
    poly([(x+.025,y+.035) for x,y in outer],fill='#070d18',outline='')
    if card.get('gold'):
        for margin,glow in ((.07,'#59421b'),(.045,'#a37727'),(.02,'#ffe28a')):
            poly(rounded(-.5-margin,-.5-margin,.5+margin,.5+margin,.075),fill=glow,outline='')
    edge='#ffdf63' if legal else '#8393ac' if dim else '#fff0a3' if selected else '#f3f4f7'
    poly(outer,fill='#eef1f6',outline=edge,width=5 if legal else 2)
    color='#c99b38' if card.get('gold') else PALETTE[card['color']]
    poly(rounded(-.46,-.472,.46,.472,.055),fill=color,outline='')
    if not small:
        poly(ellipse(.345,.35,.10),fill='#f3f3e9',outline='#ffffff',width=1)
        poly(ellipse(.303,.305,.087),fill=color,outline='')
    ink='#243048' if card['color']=='yellow' else '#ffffff'
    kind=card['kind']
    short={'skip':'⊘','reverse':'⇄','discard':'▱','skip_all':'≫','roulette':'◉','reverse4':'↶+4'}.get(kind,LABELS.get(kind,kind))
    if card['color']=='wild' and not small:
        for j,col in enumerate(('red','yellow','green','blue')):
            pts=[(0,0)]+[(.31*math.cos(a),.265*math.sin(a)) for a in
                          [j*math.pi/2+k*math.pi/32 for k in range(17)]]
            poly(pts,fill=PALETTE[col],outline='')
        poly(ellipse(.23,.19),fill='#171f32',outline='#f2f5fa',width=1)
    text(0,0,short,.31 if len(short)<3 else .24,ink)
    if not small:
        text(-.36,-.37,short,.13,ink,anchor='w')
        text(.36,.37,short,.13,ink,anchor='e')
        name=LABELS.get(kind, '换牌' if kind=='7' else '交牌' if kind=='0' else COLOR_NAMES[card['color']])
        text(0,.285,name,.105,ink)
        if legal:
            text(0,-.39,'可出',.09,ink)
    if dim:
        poly(rounded(-.46,-.472,.46,.472,.055),fill='#000000',stipple='gray50',outline='')


def pile_hit(x,y,width,height):
    """拖放判定使用与牌桌中央相同的布局，缩放窗口后仍对齐。"""
    return abs(x-width/2)<=min(115,width*.17) and abs(y-height*.51)<=min(115,height*.4)
