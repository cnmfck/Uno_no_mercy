"""打印启动所需信息，不访问外网、不修改系统、不自动更改防火墙。"""
import platform
import socket
import sys

print('系统：', platform.platform())
print('Python：', sys.version)
print('解释器路径：', sys.executable)
print('版本检查：', '通过' if sys.version_info >= (3, 10) else '需要 Python 3.10+')
try:
    import tkinter
    print('Tk 组件：', tkinter.TkVersion)
    root = tkinter.Tk()
    root.withdraw()
    root.destroy()
    print('图形窗口检查：通过')
except Exception as exc:
    print('图形窗口检查失败：', exc)
try:
    addresses = sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    print('本机候选地址：', '、'.join(addresses))
    print('朋友应使用本机局域网 IPv4 地址；127.0.0.1 仅供本机使用。')
except OSError as exc:
    print('地址查询失败：', exc)
input('按回车关闭……')
