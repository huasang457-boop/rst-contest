# -*- coding: utf-8 -*-
"""字体与程序化贴图。

游戏不依赖任何外部图片素材，所有砖块、坦克、爆炸效果都在这里用
pygame 的绘图接口现场画出来并缓存为 Surface，保证项目单文件夹即可运行，
同时全部美术均为原创。
"""

import math

import pygame

from .settings import (QUAD, TANK_SIZE, TANK_PALETTES, UP, RIGHT, DOWN, LEFT,
                       C_BRICK, C_BRICK_DARK, C_BRICK_LIGHT,
                       C_NAME, C_NAME_DARK, C_NAME_LIGHT,
                       C_STEEL, C_STEEL_DARK, C_STEEL_LIGHT,
                       C_WATER, C_WATER_LIGHT,
                       C_TREE, C_TREE_DARK, C_TREE_LIGHT,
                       C_ACCENT, C_DANGER)

# Windows 常见中文字体，按优先级尝试
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/Deng.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    # 常见 Linux / macOS 中文字体，方便跨平台运行
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

_font_cache = {}
_tank_cache = {}
_tile_cache = {}


# --------------------------------------------------------------------------
# 字体
# --------------------------------------------------------------------------
def get_font(size, bold=False):
    """取一个支持中文的字体对象（带缓存）。"""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    font = None
    for path in _FONT_CANDIDATES:
        try:
            font = pygame.font.Font(path, size)
            break
        except Exception:
            continue
    if font is None:                       # 兜底：系统字体
        try:
            font = pygame.font.SysFont("microsoftyaheui,simhei,arial", size, bold=bold)
        except Exception:
            font = pygame.font.Font(None, size)
    if bold:
        try:
            font.set_bold(True)
        except Exception:
            pass
    _font_cache[key] = font
    return font


# --------------------------------------------------------------------------
# 地形贴图
# --------------------------------------------------------------------------
def _brick_surface(base, dark, light):
    """一小格砖墙：两行错缝砌法。"""
    s = pygame.Surface((QUAD, QUAD), pygame.SRCALPHA)
    s.fill(dark)
    half = QUAD // 2
    for row in range(2):                   # 上下两行，下行错开半块形成错缝
        y = row * half
        offset = 0 if row == 0 else -half // 2
        x = offset
        while x < QUAD:
            rect = pygame.Rect(x + 1, y + 1, half - 2, half - 2)
            rect = rect.clip(pygame.Rect(0, 0, QUAD, QUAD))
            if rect.width > 1 and rect.height > 1:
                pygame.draw.rect(s, base, rect)
                pygame.draw.line(s, light, rect.topleft, (rect.right - 1, rect.top))
                pygame.draw.line(s, light, rect.topleft, (rect.left, rect.bottom - 1))
            x += half
    return s


def _steel_surface():
    """一小格钢板：中间十字加固，四角铆钉。"""
    s = pygame.Surface((QUAD, QUAD), pygame.SRCALPHA)
    s.fill(C_STEEL_DARK)
    pygame.draw.rect(s, C_STEEL, pygame.Rect(2, 2, QUAD - 4, QUAD - 4))
    pygame.draw.line(s, C_STEEL_LIGHT, (2, 2), (QUAD - 3, 2))
    pygame.draw.line(s, C_STEEL_LIGHT, (2, 2), (2, QUAD - 3))
    pygame.draw.line(s, C_STEEL_DARK, (2, QUAD - 3), (QUAD - 3, QUAD - 3))
    c = QUAD // 2
    pygame.draw.line(s, C_STEEL_DARK, (c, 4), (c, QUAD - 5))
    pygame.draw.line(s, C_STEEL_DARK, (4, c), (QUAD - 5, c))
    for pos in ((6, 6), (QUAD - 7, 6), (6, QUAD - 7), (QUAD - 7, QUAD - 7)):
        pygame.draw.circle(s, C_STEEL_LIGHT, pos, 2)
    return s


def _water_surface(frame):
    """一小格水面，两帧波纹交替形成流动感。"""
    s = pygame.Surface((QUAD, QUAD), pygame.SRCALPHA)
    s.fill(C_WATER)
    off = 0 if frame == 0 else QUAD // 2
    for i in range(2):
        y = (i * (QUAD // 2) + off) % QUAD + 4
        pygame.draw.arc(s, C_WATER_LIGHT,
                        pygame.Rect(1, y - 5, QUAD // 2, 10), 0.6, 2.6, 2)
        pygame.draw.arc(s, C_WATER_LIGHT,
                        pygame.Rect(QUAD // 2, y - 9, QUAD // 2, 10), 0.6, 2.6, 2)
    return s


def _tree_surface():
    """一小格树林：坦克可从下方穿过，绘制在最上层。"""
    s = pygame.Surface((QUAD, QUAD), pygame.SRCALPHA)
    blobs = [(7, 8, 7), (17, 7, 6), (12, 16, 8), (5, 17, 5), (19, 17, 5)]
    for x, y, r in blobs:
        pygame.draw.circle(s, C_TREE_DARK, (x, y + 1), r)
    for x, y, r in blobs:
        pygame.draw.circle(s, C_TREE, (x, y), r - 1)
        pygame.draw.circle(s, C_TREE_LIGHT, (x - 2, y - 2), max(1, r // 3))
    return s


def _crack(surf, level=1):
    """给砖块叠裂纹。level 越大裂得越狠，用来表示剩余耐久。"""
    s = surf.copy()
    dark = (38, 22, 14)
    pygame.draw.lines(s, dark, False,
                      [(3, 2), (9, 9), (5, 14), (11, 21)], 2)
    if level >= 2:
        pygame.draw.lines(s, dark, False,
                          [(QUAD - 3, 4), (QUAD - 10, 11), (QUAD - 5, 18)], 2)
        pygame.draw.lines(s, dark, False,
                          [(QUAD - 2, QUAD - 3), (QUAD - 9, QUAD - 8)], 2)
        pygame.draw.line(s, dark, (1, QUAD - 6), (8, QUAD - 1), 2)
    return s


def get_tile(kind, frame=0):
    """按类型取地形贴图。

    kind: brick / name_brick / name_brick_cracked / steel / water / tree
    """
    key = (kind, frame)
    if key not in _tile_cache:
        if kind == "brick":
            surf = _brick_surface(C_BRICK, C_BRICK_DARK, C_BRICK_LIGHT)
        elif kind == "name_brick":
            surf = _brick_surface(C_NAME, C_NAME_DARK, C_NAME_LIGHT)
        elif kind == "name_brick_cracked":
            surf = _crack(_brick_surface(C_NAME, C_NAME_DARK, C_NAME_LIGHT), 1)
        elif kind == "name_brick_broken":
            surf = _crack(_brick_surface(C_NAME, C_NAME_DARK, C_NAME_LIGHT), 2)
        elif kind == "steel":
            surf = _steel_surface()
        elif kind == "water":
            surf = _water_surface(frame)
        elif kind == "tree":
            surf = _tree_surface()
        else:
            surf = pygame.Surface((QUAD, QUAD), pygame.SRCALPHA)
        _tile_cache[key] = surf
    return _tile_cache[key]


# --------------------------------------------------------------------------
# 基地
# --------------------------------------------------------------------------
def make_base_surface(size, destroyed=False):
    """基地图标：一面带 W 徽标的旗帜；被摧毁后变成废墟。"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    if destroyed:
        pygame.draw.rect(s, (70, 62, 58), pygame.Rect(4, size - 12, size - 8, 10))
        for i, (x, y, w, h) in enumerate([(8, size - 24, 12, 12),
                                          (size - 22, size - 20, 10, 8),
                                          (size // 2 - 4, size - 30, 9, 9)]):
            pygame.draw.rect(s, (96, 84, 76) if i % 2 else (78, 68, 62),
                             pygame.Rect(x, y, w, h))
        pygame.draw.line(s, (52, 46, 42), (10, size - 14), (size - 14, 12), 4)
        return s

    pygame.draw.rect(s, (86, 78, 70), pygame.Rect(6, size - 12, size - 12, 9))
    pygame.draw.rect(s, (118, 108, 98), pygame.Rect(6, size - 12, size - 12, 3))
    pygame.draw.rect(s, (196, 196, 204), pygame.Rect(9, 6, 4, size - 16))
    flag = pygame.Rect(13, 8, size - 22, size // 2 - 2)
    pygame.draw.rect(s, C_DANGER, flag)
    pygame.draw.rect(s, (255, 220, 180), flag, 2)
    font = get_font(max(12, flag.height - 8), bold=True)
    label = font.render("W", True, C_ACCENT)
    s.blit(label, label.get_rect(center=flag.center))
    return s


# --------------------------------------------------------------------------
# 坦克
# --------------------------------------------------------------------------
def _tank_up(palette, size):
    """画一辆朝上的坦克，其余三个朝向由旋转得到。"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    tw = max(6, int(size * 0.22))
    body_rect = pygame.Rect(tw, int(size * 0.14), size - tw * 2,
                            size - int(size * 0.24))

    for x in (0, size - tw):               # 左右履带
        track = pygame.Rect(x, 2, tw, size - 4)
        pygame.draw.rect(s, palette["dark"], track, border_radius=3)
        for y in range(4, size - 5, 5):
            pygame.draw.line(s, palette["light"], (x + 1, y), (x + tw - 2, y))

    pygame.draw.rect(s, palette["body"], body_rect, border_radius=4)
    pygame.draw.rect(s, palette["light"],
                     pygame.Rect(body_rect.x + 2, body_rect.y + 2,
                                 body_rect.width - 4, 3), border_radius=2)
    pygame.draw.rect(s, palette["turret"], body_rect, 2, border_radius=4)

    c = size // 2
    pygame.draw.rect(s, palette["dark"],
                     pygame.Rect(c - 3, 1, 6, c - 2), border_radius=2)
    pygame.draw.circle(s, palette["turret"], (c, c + 2), int(size * 0.20))
    pygame.draw.circle(s, palette["light"], (c - 2, c), max(2, int(size * 0.07)))
    return s


def get_tank(kind, direction, size=TANK_SIZE):
    """取坦克贴图。kind 见 settings.TANK_PALETTES，direction 见方向常量。"""
    key = (kind, direction, size)
    if key not in _tank_cache:
        base = _tank_up(TANK_PALETTES[kind], size)
        angle = {UP: 0, LEFT: 90, DOWN: 180, RIGHT: -90}[direction]
        _tank_cache[key] = pygame.transform.rotate(base, angle)
    return _tank_cache[key]


def make_shield_surface(size):
    """出生保护罩。"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(s, (120, 220, 255, 90), (c, c), c - 1)
    pygame.draw.circle(s, (200, 245, 255, 220), (c, c), c - 1, 2)
    for i in range(8):
        a = math.pi * 2 * i / 8
        pygame.draw.line(s, (200, 245, 255, 160),
                         (c + math.cos(a) * (c - 6), c + math.sin(a) * (c - 6)),
                         (c + math.cos(a) * (c - 1), c + math.sin(a) * (c - 1)), 2)
    return s
