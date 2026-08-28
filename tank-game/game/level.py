# -*- coding: utf-8 -*-
"""关卡地图。

【身份标识 · 原创性证明】
战场正中央的砖墙布局拼出本人姓名缩写 **W Z Q**（settings.PLAYER_INITIALS）。
字母用 6x8 的点阵定义在 LETTER_BITMAPS 中，逐点转换成砖块写入地图网格，
并单独记录在 name_quads 集合里，使用更亮的砖色渲染，保证一眼可辨。
"""

import pygame

from . import assets
from .settings import (COLS, ROWS, QUAD, EMPTY, BRICK, STEEL, WATER, TREE, BASE,
                       SOLID_FOR_TANK, SOLID_FOR_BULLET, PLAYER_INITIALS,
                       NAME_BRICK_HP, SIDE_ENEMY, UP, DOWN)

# --------------------------------------------------------------------------
# 姓名缩写点阵（6 列 x 8 行，X 表示放一块砖）
# --------------------------------------------------------------------------
LETTER_BITMAPS = {
    "W": [
        "X....X",
        "X....X",
        "X....X",
        "X....X",
        "X.XX.X",
        "X.XX.X",
        "XX..XX",
        ".X..X.",
    ],
    "Z": [
        "XXXXXX",
        "....XX",
        "...XX.",
        "..XX..",
        "..XX..",
        ".XX...",
        "XX....",
        "XXXXXX",
    ],
    "Q": [
        ".XXXX.",
        "XX..XX",
        "XX..XX",
        "XX..XX",
        "XX..XX",
        "XX.XXX",
        ".XXXXX",
        "....XX",
    ],
}

LETTER_W = 6          # 单个字母宽（格）
LETTER_H = 8          # 单个字母高（格）
LETTER_GAP = 2        # 字母间距（格）

# 主通道：字母之间与左右两侧留出的 4 条纵向通道，以及字母上下的 2 条横向通道。
# 每条通道 2 格宽（48 像素），刚好够一辆 44 像素的坦克通过。
LANE_COLS = (0, 1, 8, 9, 16, 17, 24, 25)
LANE_ROWS = (6, 7, 16, 17)


class Level:
    """一关的地形数据与绘制。"""

    def __init__(self):
        self.grid = [[EMPTY] * COLS for _ in range(ROWS)]
        self.name_quads = set()          # 属于姓名缩写的砖块坐标 (col, row)
        self.name_hp = {}                # 姓名缩写砖块的剩余耐久
        self.base_destroyed = False
        self._build()

        # 基地：底部正中 2x2 格
        self.base_col, self.base_row = COLS // 2 - 1, ROWS - 2
        self.base_rect = pygame.Rect(self.base_col * QUAD, self.base_row * QUAD,
                                     QUAD * 2, QUAD * 2)

        # 出生点（像素坐标，左上角）
        self.enemy_spawns = [(0, 0), ((COLS // 2 - 1) * QUAD, 0),
                             ((COLS - 2) * QUAD, 0)]
        self.player_spawn = (8 * QUAD, (ROWS - 2) * QUAD)

    # ---------------- 地图生成 ----------------
    def _fill(self, c0, r0, c1, r1, tile):
        """把 [c0,c1] x [r0,r1] 的矩形区域填成指定地形（含端点）。"""
        for r in range(max(0, r0), min(ROWS - 1, r1) + 1):
            for c in range(max(0, c0), min(COLS - 1, c1) + 1):
                self.grid[r][c] = tile

    def _place_initials(self, text=PLAYER_INITIALS):
        """把姓名缩写以砖墙形式摆在战场中央。"""
        total_w = len(text) * LETTER_W + (len(text) - 1) * LETTER_GAP
        start_col = (COLS - total_w) // 2
        start_row = (ROWS - LETTER_H) // 2

        for i, ch in enumerate(text):
            bitmap = LETTER_BITMAPS.get(ch.upper())
            if not bitmap:
                continue
            base_col = start_col + i * (LETTER_W + LETTER_GAP)
            for dr, line in enumerate(bitmap):
                for dc, flag in enumerate(line):
                    if flag != "X":
                        continue
                    c, r = base_col + dc, start_row + dr
                    if 0 <= c < COLS and 0 <= r < ROWS:
                        self.grid[r][c] = BRICK
                        self.name_quads.add((c, r))
                        self.name_hp[(c, r)] = NAME_BRICK_HP

    def _build(self):
        """生成整张地图。

        地图骨架是「四纵两横」：三个字母各占 6 列，字母之间以及左右两边
        天然留出 4 条各 2 格宽的纵向通道（LANE_COLS，正好够一辆坦克通过）；
        字母上下再各留一条横向通道（LANE_ROWS）。掩体只摆在通道之外，
        最后再用 _carve_lanes() 兜底清一遍，保证整张图任何时候都是连通的，
        不会出现坦克被封死在角落里的情况。
        """
        self._place_initials()
        self._place_cover()
        self._place_base()
        self._carve_lanes()
        self._clear_spawn_zones()

    def _place_cover(self):
        """摆放掩体：钢板、砖墙、水面、树林。全部避开主通道。"""
        # 上半场：钢板与砖墙掩体
        self._fill(4, 4, 5, 5, STEEL)
        self._fill(COLS - 6, 4, COLS - 5, 5, STEEL)
        self._fill(2, 2, 3, 3, BRICK)
        self._fill(COLS - 4, 2, COLS - 3, 3, BRICK)
        self._fill(11, 3, 14, 4, BRICK)

        # 下半场：水面挡坦克但不挡炮弹，制造隔河对射的局面
        self._fill(2, 18, 5, 19, WATER)
        self._fill(COLS - 6, 18, COLS - 3, 19, WATER)
        self._fill(6, 20, 7, 21, BRICK)
        self._fill(COLS - 8, 20, COLS - 7, 21, BRICK)

        # 树林：坦克可以从下面穿过，绘制在最上层，形成埋伏点
        self._fill(0, 10, 1, 13, TREE)
        self._fill(COLS - 2, 10, COLS - 1, 13, TREE)
        self._fill(2, 21, 5, 22, TREE)
        self._fill(COLS - 6, 21, COLS - 3, 22, TREE)

    def _place_base(self):
        """基地与两层护墙。"""
        bc, br = COLS // 2 - 1, ROWS - 2
        self._fill(bc - 2, br - 2, bc + 3, ROWS - 1, BRICK)
        self._fill(bc, br, bc + 1, ROWS - 1, BASE)

    def _carve_lanes(self):
        """清空主通道上的阻挡物，保证地图连通。

        树林不阻挡坦克，基地是攻击目标，这两类保留不动。
        """
        for r in range(ROWS):
            for c in LANE_COLS:
                if self.grid[r][c] in (BRICK, STEEL, WATER):
                    self._clear(c, r)
        for r in LANE_ROWS:
            for c in range(COLS):
                if self.grid[r][c] in (BRICK, STEEL, WATER):
                    self._clear(c, r)

    def _clear(self, c, r):
        self.grid[r][c] = EMPTY
        self.name_quads.discard((c, r))
        self.name_hp.pop((c, r), None)

    def _clear_spawn_zones(self):
        """清空出生区域，避免坦克一出场就卡在墙里。"""
        for c in (0, COLS // 2 - 1, COLS - 2):
            self._fill(c, 0, c + 1, 1, EMPTY)
        self._fill(8, ROWS - 2, 9, ROWS - 1, EMPTY)

    # ---------------- 查询 ----------------
    @staticmethod
    def quads_in_rect(rect):
        """返回与矩形相交的所有格子坐标。"""
        c0 = max(0, rect.left // QUAD)
        c1 = min(COLS - 1, (rect.right - 1) // QUAD)
        r0 = max(0, rect.top // QUAD)
        r1 = min(ROWS - 1, (rect.bottom - 1) // QUAD)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                yield c, r

    def blocks_tank(self, rect):
        """矩形是否被地形挡住（坦克用）。"""
        if rect.left < 0 or rect.top < 0 or rect.right > COLS * QUAD or \
                rect.bottom > ROWS * QUAD:
            return True
        for c, r in self.quads_in_rect(rect):
            if self.grid[r][c] in SOLID_FOR_TANK:
                return True
        return False

    def tile_at(self, c, r):
        if 0 <= c < COLS and 0 <= r < ROWS:
            return self.grid[r][c]
        return STEEL

    # ---------------- 炮弹命中 ----------------
    def bullet_hit(self, rect, direction, power=1, side=SIDE_ENEMY):
        """炮弹与地形的碰撞判定。

        返回 (是否被挡住, 命中材质)，材质取值 None / 'brick' / 'steel' / 'base'。
        命中砖墙时会顺带打掉炮弹侧向的一格，这样弹道能开出坦克通得过的通道，
        手感接近经典坦克大战。

        基地只会被敌方炮弹摧毁：玩家的炮弹打在自己基地上只是被弹开，
        避免一进场手滑就自爆，这是有意为之的规则调整。
        """
        if rect.left < 0 or rect.top < 0 or rect.right > COLS * QUAD or \
                rect.bottom > ROWS * QUAD:
            return True, "steel"

        hits = [(c, r) for c, r in self.quads_in_rect(rect)
                if self.grid[r][c] in SOLID_FOR_BULLET]
        if not hits:
            return False, None

        if any(self.grid[r][c] == BASE for c, r in hits):
            if side == SIDE_ENEMY:
                self.destroy_base()
                return True, "base"
            return True, "steel"            # 我方炮弹打不穿自家基地

        material = "steel"
        broke = False
        for c, r in hits:
            if self.grid[r][c] == BRICK:
                broke = self._break_brick(c, r) or broke
                for nc, nr in self._side_quads(c, r, direction):
                    if self.tile_at(nc, nr) == BRICK:
                        broke = self._break_brick(nc, nr) or broke
            elif self.grid[r][c] == STEEL and power >= 2:
                self.grid[r][c] = EMPTY
                broke = True
        return True, "brick" if broke else material

    def _break_brick(self, c, r):
        """打掉一格砖。姓名缩写砖需要多打几次，返回本次是否真的被打掉。"""
        if (c, r) in self.name_hp:
            self.name_hp[(c, r)] -= 1
            if self.name_hp[(c, r)] > 0:
                return True                 # 只是被打裂，仍然挡路
            del self.name_hp[(c, r)]
            self.name_quads.discard((c, r))
        self.grid[r][c] = EMPTY
        return True

    @staticmethod
    def _side_quads(c, r, direction):
        """炮弹前进方向的垂直方向上相邻的格子。"""
        if direction in (UP, DOWN):
            return ((c - 1, r), (c + 1, r))
        return ((c, r - 1), (c, r + 1))

    def destroy_base(self):
        self.base_destroyed = True
        for c, r in list(self.quads_in_rect(self.base_rect)):
            if self.grid[r][c] == BASE:
                self.grid[r][c] = EMPTY

    # ---------------- 绘制 ----------------
    def draw_ground(self, surf, offset=(0, 0), water_frame=0):
        """绘制地面层：砖墙、钢板、水面、基地。树林另外画在最上层。"""
        ox, oy = offset
        for r in range(ROWS):
            row = self.grid[r]
            for c in range(COLS):
                tile = row[c]
                if tile in (EMPTY, TREE, BASE):
                    continue
                if tile == BRICK:
                    if (c, r) in self.name_quads:
                        hp = self.name_hp.get((c, r), NAME_BRICK_HP)
                        kind = ("name_brick" if hp >= NAME_BRICK_HP
                                else "name_brick_cracked" if hp == NAME_BRICK_HP - 1
                                else "name_brick_broken")
                    else:
                        kind = "brick"
                elif tile == STEEL:
                    kind = "steel"
                else:
                    kind = "water"
                img = assets.get_tile(kind, water_frame if kind == "water" else 0)
                surf.blit(img, (ox + c * QUAD, oy + r * QUAD))

        base_img = assets.make_base_surface(QUAD * 2, self.base_destroyed)
        surf.blit(base_img, (ox + self.base_rect.x, oy + self.base_rect.y))

    def draw_overlay(self, surf, offset=(0, 0)):
        """绘制树林层（坦克从树下穿过，形成伏击点）。"""
        ox, oy = offset
        tree = assets.get_tile("tree")
        for r in range(ROWS):
            row = self.grid[r]
            for c in range(COLS):
                if row[c] == TREE:
                    surf.blit(tree, (ox + c * QUAD, oy + r * QUAD))

    # ---------------- 统计 ----------------
    def initials_remaining(self):
        """姓名缩写还剩多少块砖（用于界面显示完成度）。"""
        return len(self.name_quads)
