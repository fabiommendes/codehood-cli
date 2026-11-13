import pyxel
from ball import bounce_pos, bounce_vel

W = 160
H = 120
R = 6
pyxel.init(W, H, title="Bola")
x = 40
y = 30
vx = 3
vy = 2


def update():
    global x, y, vx, vy
    # A nova velocidade usa a posição antiga, por isso é calculada primeiro.
    new_vx = bounce_vel(x, vx, R, W)
    new_vy = bounce_vel(y, vy, R, H)
    x = bounce_pos(x, vx, R, W)
    y = bounce_pos(y, vy, R, H)
    vx = new_vx
    vy = new_vy


def draw():
    pyxel.cls(1)
    pyxel.circ(x, y, R, 8)


pyxel.run(update, draw)
