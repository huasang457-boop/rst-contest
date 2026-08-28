# -*- coding: utf-8 -*-
"""全局常量配置。

所有可调数值集中在此，方便统一改动，避免魔法数字散落各处。
"""

# ---------------- 画面尺寸 ----------------
QUAD = 24                                    # 地图最小单元（一小块砖）
COLS, ROWS = 26, 24                          # 战场网格数
FIELD_W, FIELD_H = COLS * QUAD, ROWS * QUAD  # 战场像素尺寸 624 x 576

MARGIN = 12                                  # 窗口留白
PANEL_W = 220                                # 右侧信息栏宽度
FIELD_X, FIELD_Y = MARGIN, MARGIN            # 战场左上角坐标
PANEL_X = MARGIN * 2 + FIELD_W               # 信息栏左上角 x
WIN_W = MARGIN * 3 + FIELD_W + PANEL_W       # 窗口宽 880
WIN_H = MARGIN * 2 + FIELD_H                 # 窗口高 600

FPS = 60
TITLE = "坦克大战 · WZQ"

# ---------------- 实体参数 ----------------
TANK_SIZE = 44               # 坦克边长（略小于两格 48，转弯留余量）
BULLET_SIZE = 8

PLAYER_SPEED = 2.3           # 像素/帧
ENEMY_SPEED_NORMAL = 1.35
ENEMY_SPEED_FAST = 2.1
PLAYER_BULLET_SPEED = 7.5
ENEMY_BULLET_SPEED = 5.0

PLAYER_LIVES = 3
PLAYER_RELOAD = 0.30         # 秒，玩家射击冷却
PLAYER_MAX_BULLETS = 2       # 同屏最多几发我方炮弹
ENEMY_RELOAD_MIN = 1.1
ENEMY_RELOAD_MAX = 2.6

# 中央姓名缩写砖墙做了加固：需要命中 NAME_BRICK_HP 次才会被打掉，
# 保证「身份标识」在整局游戏里都保持可辨认。
NAME_BRICK_HP = 3

TOTAL_ENEMIES = 12           # 本关敌人总数
MAX_ALIVE_ENEMIES = 4        # 同屏最大敌人数
ENEMY_SPAWN_INTERVAL = 2.4   # 秒，敌人出生间隔
RESPAWN_PROTECT = 2.0        # 秒，出生保护时间
PLAYER_RESPAWN_DELAY = 1.4   # 秒，玩家阵亡后复活延迟

# ---------------- 地图元素 ----------------
EMPTY, BRICK, STEEL, WATER, TREE, BASE = range(6)

# 会挡住坦克的地形
SOLID_FOR_TANK = (BRICK, STEEL, WATER, BASE)
# 会挡住炮弹的地形（水面可以让炮弹飞过去）
SOLID_FOR_BULLET = (BRICK, STEEL, BASE)

# ---------------- 方向 ----------------
UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3
DIR_VEC = {UP: (0, -1), RIGHT: (1, 0), DOWN: (0, 1), LEFT: (-1, 0)}
ALL_DIRS = (UP, RIGHT, DOWN, LEFT)

# ---------------- 阵营 ----------------
SIDE_PLAYER, SIDE_ENEMY = "player", "enemy"

# ---------------- 得分 ----------------
SCORE_PER_ENEMY = {"normal": 100, "fast": 200, "armor": 300}

# ---------------- 配色 ----------------
C_BG = (18, 20, 28)              # 窗口底色
C_PANEL = (26, 30, 42)           # 信息栏底色
C_PANEL_LINE = (58, 66, 88)
C_TEXT = (228, 232, 240)
C_TEXT_DIM = (140, 150, 172)
C_ACCENT = (255, 196, 66)        # 主强调色（金）
C_ACCENT2 = (86, 204, 242)       # 次强调色（蓝）
C_DANGER = (240, 90, 80)
C_OK = (108, 214, 128)

# 砖墙（WZQ 字母就用这个颜色，做了高亮区分）
C_BRICK = (158, 74, 48)
C_BRICK_DARK = (104, 46, 30)
C_BRICK_LIGHT = (186, 104, 70)
# 姓名缩写专用砖色（更亮，让 WZQ 一眼可辨）
C_NAME = (242, 176, 66)
C_NAME_DARK = (172, 112, 28)
C_NAME_LIGHT = (255, 226, 150)

C_STEEL = (168, 178, 196)
C_STEEL_DARK = (104, 114, 134)
C_STEEL_LIGHT = (222, 230, 244)

C_WATER = (44, 96, 160)
C_WATER_LIGHT = (86, 156, 220)

C_TREE = (46, 122, 66)
C_TREE_DARK = (28, 84, 46)
C_TREE_LIGHT = (96, 172, 92)

# 坦克配色（body 车身 / dark 履带 / light 高光 / turret 炮塔）
TANK_PALETTES = {
    "player": {"body": (214, 196, 92), "dark": (96, 88, 40),
               "light": (245, 234, 160), "turret": (176, 158, 64)},
    "normal": {"body": (188, 194, 206), "dark": (86, 92, 104),
               "light": (232, 238, 248), "turret": (150, 156, 170)},
    "fast":   {"body": (128, 200, 216), "dark": (46, 96, 110),
               "light": (196, 240, 250), "turret": (92, 168, 186)},
    "armor":  {"body": (206, 104, 96), "dark": (108, 44, 40),
               "light": (248, 168, 158), "turret": (172, 74, 68)},
}

# 敌人类型 -> (速度, 血量, 炮弹速度)
ENEMY_TYPES = {
    "normal": (ENEMY_SPEED_NORMAL, 1, ENEMY_BULLET_SPEED),
    "fast":   (ENEMY_SPEED_FAST, 1, ENEMY_BULLET_SPEED + 1.2),
    "armor":  (ENEMY_SPEED_NORMAL * 0.85, 3, ENEMY_BULLET_SPEED),
}

# ---------------- 身份标识 ----------------
PLAYER_INITIALS = "WZQ"          # 本人姓名缩写，用于地图布局与界面标识
CAMPUS_NAME = "浩源 · 浪尖儿大学生社区"
