"""四向选色盘。鼠标点击扇区确认；方向键选中，回车确认，退出键取消。"""
import tkinter as tk
import math

INK = {'red':'#ec5367','yellow':'#f3cc60','green':'#53cca4','blue':'#609bfa'}
NAMES = {'red':'红色','yellow':'黄色','green':'绿色','blue':'蓝色'}
DIRECTIONS = ('red','blue','green','yellow')  # 上、右、下、左


def sector(x,y):
    dx,dy=x-230,y-230
    if not 75 <= math.hypot(dx,dy) <= 200:
        return None
    return DIRECTIONS[int(((math.atan2(dy,dx)+math.pi/2+math.pi/4) % math.tau)/(math.pi/2))]


def open_wheel(app, callback):
    if app.dialog and app.dialog.winfo_exists():
        app.dialog.lift()
        return
    win=tk.Toplevel(app.root)
    app.dialog=win
    win.title('选择颜色')
    win.resizable(False,False)
    win.transient(app.root)
    win.configure(bg='#101827')
    win.geometry(f'460x510+{app.root.winfo_rootx()+(app.root.winfo_width()-460)//2}+{app.root.winfo_rooty()+(app.root.winfo_height()-510)//2}')
    canvas=tk.Canvas(win,width=460,height=460,bg='#101827',highlightthickness=0)
    canvas.pack()
    selected=['red']
    def close():
        app.dialog=None
        win.destroy()
    def finish(color):
        if color:
            close()
            callback(color)
    def draw():
        canvas.delete('all')
        for i,color in enumerate(DIRECTIONS):
            canvas.create_arc(30,30,430,430,start=45-i*90,extent=90,fill=INK[color],outline='white' if selected[0]==color else '#101827',width=6)
            angle=-math.pi/2+i*math.pi/2
            canvas.create_text(230+math.cos(angle)*140,230+math.sin(angle)*140,text=NAMES[color],fill='#152033',font=('Microsoft YaHei UI',22,'bold'))
        canvas.create_oval(155,155,305,305,fill='#101827',outline='#e4efff',width=2)
        canvas.create_text(230,215,text='选择颜色',fill='white',font=('Microsoft YaHei UI',18,'bold'))
        canvas.create_text(230,247,text=NAMES[selected[0]],fill=INK[selected[0]],font=('Microsoft YaHei UI',14))
    def choose(color):
        if color:
            selected[0]=color
            draw()
    canvas.bind('<Motion>',lambda e:choose(sector(e.x,e.y)))
    canvas.bind('<Button-1>',lambda e:finish(sector(e.x,e.y)))
    for key,color in zip(('Up','Right','Down','Left'),DIRECTIONS):
        win.bind('<'+key+'>',lambda e,color=color:choose(color))
    win.bind('<Return>',lambda e:finish(selected[0]))
    win.bind('<Escape>',lambda e:close())
    win.protocol('WM_DELETE_WINDOW',close)
    tk.Label(win,text='点击扇区确认 · 方向键选择 / 回车确认 · 退出键取消',bg='#101827',fg='#b7c6db').pack(pady=10)
    draw()
    win.grab_set()
    win.focus_set()
