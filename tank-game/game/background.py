# -*- coding: utf-8 -*-
"""原创校园底图。

战场底图是一张现画的「浩源 · 浪尖儿大学生社区」校园黄昏场景：
远景山脊 → 教学楼群 → 主楼与校名招牌 → 操场跑道 → 行道树，
最后压一层半透明暗色，保证游戏元素在底图之上依然清晰可读。

全部图形由 pygame.draw 生成，不使用任何第三方图片素材，属原创作品。
"""

import math
import random

import pygame

from . import assets
from .settings import QUAD, CAMPUS_NAME, PLAYER_INITIALS


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def _vertical_gradient(surf, rect, top_color, bottom_color):
    """在 rect 区域内画垂直渐变。"""
    x, y, w, h = rect
    for i in range(h):
        t = i / max(1, h - 1)
        color = tuple(int(top_color[k] + (bottom_color[k] - top_color[k]) * t)
                      for k in range(3))
        pygame.draw.line(surf, color, (x, y + i), (x + w, y + i))


def _hill(surf, width, base_y, amplitude, color, seed, steps=26):
    """画一条起伏的山脊线并填充到底部。"""
    rnd = random.Random(seed)
    points = [(0, base_y)]
    for i in range(steps + 1):
        x = width * i / steps
        y = base_y - amplitude * (0.45 + 0.55 * abs(math.sin(i * 0.7 + seed)))
        y += rnd.uniform(-amplitude * 0.12, amplitude * 0.12)
        points.append((x, y))
    points.append((width, base_y))
    pygame.draw.polygon(surf, color, points)


def _building(surf, rect, body, roof, window, seed, lit_ratio=0.55):
    """一栋教学楼：楼体 + 楼顶 + 亮灯窗户。"""
    rnd = random.Random(seed)
    pygame.draw.rect(surf, body, rect)
    pygame.draw.rect(surf, roof, pygame.Rect(rect.x - 3, rect.y - 5,
                                             rect.width + 6, 6))
    cols = max(2, rect.width // 13)
    rows = max(2, rect.height // 16)
    pad_x = (rect.width - cols * 7) / (cols + 1)
    pad_y = (rect.height - rows * 9) / (rows + 1)
    for r in range(rows):
        for c in range(cols):
            wx = rect.x + pad_x + c * (7 + pad_x)
            wy = rect.y + pad_y + r * (9 + pad_y)
            color = window if rnd.random() < lit_ratio else (46, 52, 74)
            pygame.draw.rect(surf, color, pygame.Rect(int(wx), int(wy), 6, 8))


def _tree(surf, x, base_y, scale, trunk, leaf, leaf_dark):
    """行道树。"""
    h = int(22 * scale)
    pygame.draw.rect(surf, trunk,
                     pygame.Rect(int(x - 2 * scale), base_y - h,
                                 max(2, int(4 * scale)), h))
    for dx, dy, r in ((0, -h - 6, 11), (-8, -h + 1, 8), (8, -h + 1, 8)):
        pygame.draw.circle(surf, leaf_dark,
                           (int(x + dx * scale), int(base_y + dy * scale) + 2),
                           int(r * scale))
    for dx, dy, r in ((0, -h - 6, 10), (-8, -h + 1, 7), (8, -h + 1, 7)):
        pygame.draw.circle(surf, leaf,
                           (int(x + dx * scale), int(base_y + dy * scale)),
                           int(r * scale))


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------
def make_campus_background(width, height, dim=118):
    """生成战场底图。dim 为压暗程度（0~255），越大战场越暗、游戏元素越清晰。"""
    surf = pygame.Surface((width, height)).convert_alpha()

    horizon = int(height * 0.46)

    # 1) 黄昏天空
    _vertical_gradient(surf, (0, 0, width, horizon),
                       (38, 52, 96), (232, 152, 104))

    # 2) 夕阳
    sun_x, sun_y = int(width * 0.74), int(horizon * 0.62)
    for r, alpha in ((78, 28), (58, 40), (40, 70)):
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 214, 150, alpha), (r, r), r)
        surf.blit(glow, (sun_x - r, sun_y - r))
    pygame.draw.circle(surf, (255, 236, 196), (sun_x, sun_y), 24)

    # 3) 远山
    _hill(surf, width, horizon + 6, 46, (58, 66, 104), seed=3)
    _hill(surf, width, horizon + 16, 32, (44, 54, 88), seed=9)

    # 4) 教学楼群（远景剪影）
    far = [(20, 58, 74), (36, 46, 92), (118, 52, 62), (196, 44, 84),
           (262, 50, 70), (330, 40, 96), (398, 56, 66), (470, 46, 88),
           (544, 52, 72)]
    for i, (bx, bw, bh) in enumerate(far):
        rect = pygame.Rect(int(bx * width / 624), horizon - bh,
                           int(bw * width / 624), bh)
        _building(surf, rect, (52, 58, 88), (40, 46, 72), (255, 208, 132),
                  seed=i, lit_ratio=0.42)

    # 5) 主楼：浩源教学主楼
    main = pygame.Rect(int(width * 0.30), horizon - 132,
                       int(width * 0.40), 132)
    _building(surf, main, (72, 76, 108), (56, 60, 88), (255, 222, 150),
              seed=42, lit_ratio=0.62)
    # 校名横幅：放在战场顶部空域，不会被砖墙挡住
    _campus_banner(surf, width, int(height * 0.095))

    # 6) 地面
    _vertical_gradient(surf, (0, horizon, width, height - horizon),
                       (46, 78, 56), (26, 46, 36))

    # 7) 操场跑道
    track_rect = pygame.Rect(int(width * 0.10), horizon + 44,
                             int(width * 0.80), int(height * 0.40))
    pygame.draw.ellipse(surf, (150, 74, 54), track_rect)
    inner = track_rect.inflate(-46, -34)
    pygame.draw.ellipse(surf, (172, 92, 66), inner)
    pygame.draw.ellipse(surf, (58, 106, 62), inner.inflate(-40, -30))
    pygame.draw.ellipse(surf, (232, 232, 232), inner, 2)
    pygame.draw.ellipse(surf, (232, 232, 232), inner.inflate(-40, -30), 2)
    # 跑道分道线
    for i in range(12):
        a = math.pi * 2 * i / 12
        cx, cy = inner.center
        rx, ry = inner.width / 2, inner.height / 2
        p1 = (cx + math.cos(a) * rx * 0.80, cy + math.sin(a) * ry * 0.80)
        p2 = (cx + math.cos(a) * rx, cy + math.sin(a) * ry)
        pygame.draw.line(surf, (226, 226, 226), p1, p2, 1)

    # 8) 校道与行道树
    road_y = horizon + 22
    pygame.draw.rect(surf, (96, 96, 104), pygame.Rect(0, road_y, width, 16))
    for x in range(10, width, 46):
        pygame.draw.line(surf, (222, 222, 222), (x, road_y + 8), (x + 18, road_y + 8), 2)
    for i, x in enumerate(range(24, width, 78)):
        _tree(surf, x, road_y + 2, 1.0 + (i % 3) * 0.12,
              (86, 62, 46), (74, 142, 78), (48, 104, 58))

    # 9) 底部草坪上的姓名缩写标识（第二重身份标识）
    big = assets.get_font(120, bold=True)
    mark = big.render(PLAYER_INITIALS, True, (255, 255, 255))
    mark.set_alpha(26)
    surf.blit(mark, mark.get_rect(center=(width // 2, int(height * 0.80))))

    # 10) 压暗 + 暗角，保证战场元素清晰
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((10, 14, 24, dim))
    surf.blit(shade, (0, 0))
    _vignette(surf, width, height)

    # 11) 极淡的网格，帮助玩家判断格子对齐
    grid = pygame.Surface((width, height), pygame.SRCALPHA)
    for x in range(0, width, QUAD * 2):
        pygame.draw.line(grid, (255, 255, 255, 10), (x, 0), (x, height))
    for y in range(0, height, QUAD * 2):
        pygame.draw.line(grid, (255, 255, 255, 10), (0, y), (width, y))
    surf.blit(grid, (0, 0))

    return surf


def _campus_banner(surf, width, cy):
    """顶部校名横幅：两侧立柱 + 中间灯箱。"""
    font = assets.get_font(16, bold=True)
    label = font.render(CAMPUS_NAME, True, (255, 214, 140))
    box = pygame.Rect(0, 0, label.get_width() + 40, label.get_height() + 14)
    box.center = (width // 2, cy)

    for x in (box.left - 10, box.right + 4):        # 立柱
        pygame.draw.rect(surf, (58, 50, 46), pygame.Rect(x, box.top - 4, 7, 34))
    pygame.draw.rect(surf, (24, 28, 42), box, border_radius=5)
    pygame.draw.rect(surf, (255, 176, 82), box, 2, border_radius=5)
    surf.blit(label, label.get_rect(center=box.center))
    for i in range(6):                              # 灯箱上的小灯
        pygame.draw.circle(surf, (255, 224, 160),
                           (box.left + 10 + i * (box.width - 20) // 5, box.top - 5), 2)


def _vignette(surf, width, height, strength=110):
    """四周压暗的暗角效果。"""
    vig = pygame.Surface((width, height), pygame.SRCALPHA)
    steps = 26
    for i in range(steps):
        t = i / steps
        alpha = int(strength * (t ** 2))
        rect = pygame.Rect(int(width * t * 0.06), int(height * t * 0.06), 0, 0)
        rect.width = width - rect.x * 2
        rect.height = height - rect.y * 2
        pygame.draw.rect(vig, (6, 8, 16, alpha // steps + 1), rect,
                         max(1, int(width * 0.03)), border_radius=18)
    surf.blit(vig, (0, 0))
