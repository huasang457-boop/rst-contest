# -*- coding: utf-8 -*-
"""右侧信息栏与各种状态提示界面。

界面上始终显示姓名缩写 WZQ 徽标（身份标识加分项之一），
并实时统计中央缩写砖墙的完好程度。
"""

import pygame

from . import assets
from .settings import (PANEL_X, PANEL_W, MARGIN, WIN_H, FIELD_X, FIELD_Y,
                       FIELD_W, FIELD_H, UP, DOWN,
                       C_PANEL, C_PANEL_LINE, C_TEXT, C_TEXT_DIM, C_ACCENT,
                       C_ACCENT2, C_DANGER, C_OK, PLAYER_INITIALS, CAMPUS_NAME,
                       TOTAL_ENEMIES)


def _text(surf, text, pos, size=16, color=C_TEXT, bold=False, center=False):
    font = assets.get_font(size, bold=bold)
    img = font.render(text, True, color)
    rect = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
    surf.blit(img, rect)
    return rect


def _section(surf, title, y):
    """小节标题 + 分隔线，返回下一行的 y。"""
    _text(surf, title, (PANEL_X + 14, y), 13, C_TEXT_DIM, bold=True)
    y += 19
    pygame.draw.line(surf, C_PANEL_LINE, (PANEL_X + 14, y),
                     (PANEL_X + PANEL_W - 14, y))
    return y + 9


class Hud:
    """信息栏绘制。"""

    def __init__(self):
        self.panel_rect = pygame.Rect(PANEL_X, MARGIN, PANEL_W, WIN_H - MARGIN * 2)

    # ------------------------------------------------------------------
    def draw_panel(self, surf, game):
        pygame.draw.rect(surf, C_PANEL, self.panel_rect, border_radius=10)
        pygame.draw.rect(surf, C_PANEL_LINE, self.panel_rect, 2, border_radius=10)

        x = PANEL_X + 14
        y = MARGIN + 14

        # ---- 标题 ----
        _text(surf, "坦克大战", (x, y), 24, C_ACCENT, bold=True)
        y += 30
        _text(surf, "TANK BATTLE", (x, y), 12, C_TEXT_DIM)
        y += 22

        # ---- 身份标识徽标 ----
        badge = pygame.Rect(x, y, PANEL_W - 28, 46)
        pygame.draw.rect(surf, (44, 38, 22), badge, border_radius=8)
        pygame.draw.rect(surf, C_ACCENT, badge, 2, border_radius=8)
        _text(surf, PLAYER_INITIALS, (badge.x + 14, badge.y + 8), 26,
              C_ACCENT, bold=True)
        _text(surf, "本人姓名缩写", (badge.x + 88, badge.y + 8), 12, C_TEXT_DIM)
        _text(surf, "地图中央同款布局", (badge.x + 88, badge.y + 25), 12, C_TEXT_DIM)
        y = badge.bottom + 16

        # ---- 战况 ----
        y = _section(surf, "战况", y)
        _text(surf, "得分", (x, y), 15, C_TEXT_DIM)
        score_img = assets.get_font(17, bold=True).render(str(game.score), True, C_ACCENT2)
        surf.blit(score_img, score_img.get_rect(topright=(PANEL_X + PANEL_W - 14, y - 1)))
        y += 26

        _text(surf, "剩余生命", (x, y), 15, C_TEXT_DIM)
        for i in range(max(0, game.lives)):
            icon = assets.get_tank("player", UP, 18)
            surf.blit(icon, (PANEL_X + PANEL_W - 20 - i * 21, y - 1))
        y += 28

        _text(surf, "剩余敌军 %d" % game.enemies_left(), (x, y), 15, C_TEXT_DIM)
        y += 22
        self._draw_enemy_icons(surf, game, x, y)
        y += 44

        # ---- 缩写完好度 ----
        y = _section(surf, "缩写砖墙完好度", y)
        total = max(1, game.initials_total)
        left = game.level.initials_remaining()
        ratio = left / total
        bar = pygame.Rect(x, y, PANEL_W - 28, 12)
        pygame.draw.rect(surf, (40, 44, 58), bar, border_radius=6)
        fill = bar.copy()
        fill.width = int(bar.width * ratio)
        color = C_OK if ratio > 0.6 else (C_ACCENT if ratio > 0.3 else C_DANGER)
        if fill.width > 0:
            pygame.draw.rect(surf, color, fill, border_radius=6)
        y += 17
        _text(surf, "%d / %d 块" % (left, total), (x, y), 12, C_TEXT_DIM)
        y += 26

        # ---- 操作说明 ----
        y = _section(surf, "操作", y)
        for key, desc in (("W A S D / ↑←↓→", "移动"),
                          ("空格 / J", "开炮"),
                          ("P", "暂停"),
                          ("R", "重新开始"),
                          ("F1", "保存截图"),
                          ("ESC", "退出")):
            _text(surf, key, (x, y), 13, C_TEXT)
            key_img = assets.get_font(13).render(desc, True, C_TEXT_DIM)
            surf.blit(key_img, key_img.get_rect(topright=(PANEL_X + PANEL_W - 14, y)))
            y += 19

        # ---- 页脚 ----
        foot_y = self.panel_rect.bottom - 40
        pygame.draw.line(surf, C_PANEL_LINE, (x, foot_y),
                         (PANEL_X + PANEL_W - 14, foot_y))
        _text(surf, CAMPUS_NAME, (x, foot_y + 8), 12, C_TEXT_DIM)
        _text(surf, "原创作品 · %s" % PLAYER_INITIALS, (x, foot_y + 24), 12, C_TEXT_DIM)

    def _draw_enemy_icons(self, surf, game, x, y):
        """用小坦克图标表示还没出场 + 场上存活的敌人。"""
        remaining = game.enemies_left()
        per_row = 9
        for i in range(min(remaining, TOTAL_ENEMIES)):
            icon = assets.get_tank("normal", DOWN, 16)
            ix = x + (i % per_row) * 19
            iy = y + (i // per_row) * 20
            surf.blit(icon, (ix, iy))

    # ------------------------------------------------------------------
    def draw_overlay(self, surf, game):
        """在战场区域上叠加菜单 / 暂停 / 胜负画面。"""
        if game.state == "playing":
            return

        field = pygame.Rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
        veil = pygame.Surface((FIELD_W, FIELD_H), pygame.SRCALPHA)
        veil.fill((8, 10, 18, 205))
        surf.blit(veil, field.topleft)

        cx = field.centerx
        cy = field.centery

        if game.state == "menu":
            _text(surf, "坦克大战", (cx, cy - 130), 52, C_ACCENT, bold=True, center=True)
            _text(surf, CAMPUS_NAME, (cx, cy - 82), 18, C_TEXT_DIM, center=True)
            self._initials_preview(surf, (cx, cy - 18))
            _text(surf, "战场中央的砖墙拼出作者姓名缩写 %s" % PLAYER_INITIALS,
                  (cx, cy + 52), 15, C_TEXT_DIM, center=True)
            _text(surf, "按 空格 / 回车 开始战斗", (cx, cy + 100), 22, C_TEXT,
                  bold=True, center=True)
            _text(surf, "WASD / 方向键 移动    空格 开炮    P 暂停",
                  (cx, cy + 136), 14, C_TEXT_DIM, center=True)

        elif game.state == "paused":
            _text(surf, "暂 停", (cx, cy - 30), 46, C_ACCENT, bold=True, center=True)
            _text(surf, "按 P 继续，R 重新开始", (cx, cy + 30), 18, C_TEXT_DIM,
                  center=True)

        elif game.state == "win":
            _text(surf, "任务完成", (cx, cy - 92), 48, C_OK, bold=True, center=True)
            _text(surf, "全部敌军已被歼灭", (cx, cy - 42), 20, C_TEXT, center=True)
            self._result_lines(surf, game, cx, cy)

        elif game.state == "lose":
            reason = "基地被摧毁" if game.level.base_destroyed else "生命耗尽"
            _text(surf, "战斗失败", (cx, cy - 92), 48, C_DANGER, bold=True, center=True)
            _text(surf, reason, (cx, cy - 42), 20, C_TEXT, center=True)
            self._result_lines(surf, game, cx, cy)

    def _result_lines(self, surf, game, cx, cy):
        total = max(1, game.initials_total)
        left = game.level.initials_remaining()
        _text(surf, "最终得分  %d" % game.score, (cx, cy + 6), 26, C_ACCENT,
              bold=True, center=True)
        _text(surf, "击毁敌军  %d / %d" % (game.killed, TOTAL_ENEMIES),
              (cx, cy + 44), 17, C_TEXT_DIM, center=True)
        _text(surf, "%s 缩写砖墙完好  %d%%" % (PLAYER_INITIALS,
                                          int(left * 100 / total)),
              (cx, cy + 70), 17, C_TEXT_DIM, center=True)
        _text(surf, "按 R 再来一局    ESC 退出", (cx, cy + 116), 18, C_TEXT,
              bold=True, center=True)

    def _initials_preview(self, surf, center):
        """菜单里画一个 WZQ 砖墙缩略图，直观说明身份标识。"""
        from .level import LETTER_BITMAPS, LETTER_W, LETTER_H, LETTER_GAP
        cell = 6
        total_w = (len(PLAYER_INITIALS) * LETTER_W +
                   (len(PLAYER_INITIALS) - 1) * LETTER_GAP) * cell
        total_h = LETTER_H * cell
        ox = center[0] - total_w // 2
        oy = center[1] - total_h // 2
        for i, ch in enumerate(PLAYER_INITIALS):
            bitmap = LETTER_BITMAPS.get(ch.upper())
            if not bitmap:
                continue
            bx = ox + i * (LETTER_W + LETTER_GAP) * cell
            for r, line in enumerate(bitmap):
                for c, flag in enumerate(line):
                    if flag == "X":
                        pygame.draw.rect(
                            surf, C_ACCENT,
                            pygame.Rect(bx + c * cell, oy + r * cell,
                                        cell - 1, cell - 1))
