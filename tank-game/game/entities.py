# -*- coding: utf-8 -*-
"""游戏实体：坦克、子弹、爆炸、飘字。

坐标统一用浮点保存（self.x / self.y），再同步到整数矩形 self.rect 做碰撞，
这样低速移动不会因为取整而丢失位移。
"""

import math
import random

import pygame

from . import assets
from .settings import (QUAD, TANK_SIZE, BULLET_SIZE, DIR_VEC, ALL_DIRS,
                       UP, RIGHT, DOWN, LEFT, SIDE_PLAYER, SIDE_ENEMY,
                       ENEMY_TYPES, ENEMY_RELOAD_MIN, ENEMY_RELOAD_MAX,
                       C_ACCENT, C_DANGER, C_OK)


# ==========================================================================
# 子弹
# ==========================================================================
class Bullet:
    """一发炮弹。"""

    def __init__(self, x, y, direction, speed, side, power=1):
        self.x, self.y = float(x), float(y)
        self.direction = direction
        self.speed = speed
        self.side = side
        self.power = power
        self.alive = True
        self.rect = pygame.Rect(0, 0, BULLET_SIZE, BULLET_SIZE)
        self.rect.center = (int(x), int(y))
        self.trail = []                      # 拖尾，用于绘制

    def update(self, level):
        """按速度前进；返回命中的材质（None 表示没撞到地形）。

        为避免高速穿墙，把一帧的位移拆成若干小步逐步检测。
        """
        dx, dy = DIR_VEC[self.direction]
        steps = max(1, int(math.ceil(self.speed / 4.0)))
        step_len = self.speed / steps

        self.trail.append(self.rect.center)
        if len(self.trail) > 4:
            self.trail.pop(0)

        for _ in range(steps):
            self.x += dx * step_len
            self.y += dy * step_len
            self.rect.center = (int(round(self.x)), int(round(self.y)))
            blocked, material = level.bullet_hit(self.rect, self.direction,
                                                 self.power, self.side)
            if blocked:
                self.alive = False
                return material
        return None

    def draw(self, surf):
        # 拖尾
        for i, pos in enumerate(self.trail):
            alpha_r = max(1, BULLET_SIZE // 2 - (len(self.trail) - i - 1))
            color = (255, 200, 120) if self.side == SIDE_PLAYER else (255, 150, 140)
            pygame.draw.circle(surf, color, pos, alpha_r)
        color = (255, 236, 190) if self.side == SIDE_PLAYER else (255, 190, 180)
        pygame.draw.circle(surf, color, self.rect.center, BULLET_SIZE // 2)
        pygame.draw.circle(surf, (255, 255, 255), self.rect.center,
                           max(1, BULLET_SIZE // 4))


# ==========================================================================
# 坦克基类
# ==========================================================================
class Tank:
    """坦克基类，玩家与敌人共用移动、开火、绘制逻辑。"""

    def __init__(self, x, y, kind, side, direction=UP):
        speed, hp, bullet_speed = ENEMY_TYPES.get(kind, (2.3, 1, 7.5))
        self.kind = kind
        self.side = side
        self.speed = speed
        self.max_hp = hp
        self.hp = hp
        self.bullet_speed = bullet_speed

        self.x, self.y = float(x), float(y)
        self.rect = pygame.Rect(int(x), int(y), TANK_SIZE, TANK_SIZE)
        self.direction = direction
        self.moving = False
        self.alive = True
        self.shield_time = 0.0               # 出生保护剩余秒数
        self.reload_time = 0.0
        self.tread_phase = 0.0               # 履带动画相位

    # ---------------- 位置同步 ----------------
    def _sync(self):
        self.rect.x = int(round(self.x))
        self.rect.y = int(round(self.y))

    def _place(self, x, y):
        self.x, self.y = float(x), float(y)
        self._sync()

    # ---------------- 移动 ----------------
    def _collides(self, rect, level, others):
        if level.blocks_tank(rect):
            return True
        for other in others:
            if other is not self and other.alive and rect.colliderect(other.rect):
                return True
        return False

    def turn(self, direction, level, others):
        """转向。转向时把垂直方向坐标吸附到网格，避免卡在墙角进不去通道。"""
        if direction == self.direction:
            return
        self.direction = direction
        old_x, old_y = self.x, self.y
        if direction in (UP, DOWN):
            self.x = round(self.x / QUAD) * QUAD
        else:
            self.y = round(self.y / QUAD) * QUAD
        self._sync()
        if self._collides(self.rect, level, others):   # 吸附后撞墙则还原
            self._place(old_x, old_y)

    def advance(self, level, others, dt):
        """沿当前朝向前进一步，返回是否真的移动了。"""
        dx, dy = DIR_VEC[self.direction]
        nx, ny = self.x + dx * self.speed, self.y + dy * self.speed
        test = pygame.Rect(int(round(nx)), int(round(ny)), TANK_SIZE, TANK_SIZE)
        if self._collides(test, level, others):
            return False
        self._place(nx, ny)
        self.moving = True
        self.tread_phase = (self.tread_phase + self.speed * dt * 8) % 4
        return True

    # ---------------- 开火 ----------------
    def can_fire(self):
        return self.alive and self.reload_time <= 0

    def make_bullet(self, power=1):
        """在炮口位置生成一发炮弹。"""
        dx, dy = DIR_VEC[self.direction]
        cx = self.rect.centerx + dx * (TANK_SIZE // 2)
        cy = self.rect.centery + dy * (TANK_SIZE // 2)
        return Bullet(cx, cy, self.direction, self.bullet_speed, self.side, power)

    # ---------------- 受击 ----------------
    def take_damage(self, amount=1):
        """扣血，返回是否被击毁。"""
        if self.shield_time > 0:
            return False
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    # ---------------- 更新与绘制 ----------------
    def update_timers(self, dt):
        if self.reload_time > 0:
            self.reload_time = max(0.0, self.reload_time - dt)
        if self.shield_time > 0:
            self.shield_time = max(0.0, self.shield_time - dt)

    def draw(self, surf):
        if not self.alive:
            return
        img = assets.get_tank(self.kind, self.direction)
        surf.blit(img, img.get_rect(center=self.rect.center))

        # 装甲坦克显示剩余血量
        if self.max_hp > 1 and self.hp > 0:
            bar_w = TANK_SIZE - 12
            x, y = self.rect.x + 6, self.rect.y - 6
            pygame.draw.rect(surf, (40, 40, 48), (x, y, bar_w, 4), border_radius=2)
            ratio = self.hp / self.max_hp
            color = C_OK if ratio > 0.6 else (C_ACCENT if ratio > 0.3 else C_DANGER)
            pygame.draw.rect(surf, color,
                             (x, y, int(bar_w * ratio), 4), border_radius=2)

        # 出生保护罩闪烁
        if self.shield_time > 0:
            if int(self.shield_time * 12) % 2 == 0:
                shield = assets.make_shield_surface(TANK_SIZE + 10)
                surf.blit(shield, shield.get_rect(center=self.rect.center))


# ==========================================================================
# 玩家坦克
# ==========================================================================
class PlayerTank(Tank):
    """玩家坦克：速度、装弹参数来自 settings，操作由 core 转发。"""

    def __init__(self, x, y, speed, bullet_speed, reload_time):
        super().__init__(x, y, "player", SIDE_PLAYER, UP)
        self.speed = speed
        self.bullet_speed = bullet_speed
        self.reload_interval = reload_time
        self.max_hp = 1
        self.hp = 1

    def handle_input(self, pressed, level, others, dt):
        """根据按键状态移动。同时按多个方向时以最后判定到的为准。"""
        direction = None
        if pressed.get(UP):
            direction = UP
        elif pressed.get(DOWN):
            direction = DOWN
        elif pressed.get(LEFT):
            direction = LEFT
        elif pressed.get(RIGHT):
            direction = RIGHT

        self.moving = False
        if direction is None:
            return
        if direction != self.direction:
            self.turn(direction, level, others)
        self.advance(level, others, dt)


# ==========================================================================
# 敌方坦克
# ==========================================================================
class EnemyTank(Tank):
    """敌方坦克。

    AI 策略（简单但够用）：
      * 每隔一段随机时间，或撞墙时，重新选择行进方向；
      * 选方向时按权重偏向「基地」与「玩家」，其余情况随机，避免完全呆板；
      * 与玩家 / 基地处于同一行或同一列时提高开火概率。
    """

    def __init__(self, x, y, kind):
        super().__init__(x, y, kind, SIDE_ENEMY, DOWN)
        self.turn_timer = random.uniform(0.4, 1.2)
        self.reload_time = random.uniform(0.3, 1.0)
        self.score = 0

    def think(self, dt, level, others, player, base_rect):
        self.turn_timer -= dt

        moved = self.advance(level, others, dt)
        if not moved or self.turn_timer <= 0:
            self._choose_direction(level, others, player, base_rect)
            self.turn_timer = random.uniform(0.7, 2.0)

        if self.can_fire():
            if self._should_fire(player, base_rect):
                self.reload_time = random.uniform(ENEMY_RELOAD_MIN, ENEMY_RELOAD_MAX)
                return self.make_bullet()
        return None

    def _choose_direction(self, level, others, player, base_rect):
        roll = random.random()
        if roll < 0.22:
            targets = self._dirs_toward(base_rect.centerx, base_rect.centery)
        elif roll < 0.55 and player is not None and player.alive:
            targets = self._dirs_toward(player.rect.centerx, player.rect.centery)
        else:
            targets = list(ALL_DIRS)
            random.shuffle(targets)

        for d in targets:                     # 选第一个走得通的方向
            if self._can_go(d, level, others):
                self.turn(d, level, others)
                return
        fallback = list(ALL_DIRS)
        random.shuffle(fallback)
        self.turn(fallback[0], level, others)

    def _can_go(self, direction, level, others):
        dx, dy = DIR_VEC[direction]
        probe = self.rect.move(dx * max(3, int(self.speed * 2)),
                               dy * max(3, int(self.speed * 2)))
        return not self._collides(probe, level, others)

    def _dirs_toward(self, tx, ty):
        """朝目标点的两个候选方向，主轴优先。"""
        dx = tx - self.rect.centerx
        dy = ty - self.rect.centery
        horiz = RIGHT if dx > 0 else LEFT
        vert = DOWN if dy > 0 else UP
        return [horiz, vert] if abs(dx) > abs(dy) else [vert, horiz]

    def _should_fire(self, player, base_rect):
        """瞄准玩家时果断开火；对着基地方向只是偶尔放一炮，其余时候小概率乱射。

        刻意压低了「对基地开火」的概率：不然十二辆敌人会一路压到基地把它秒了，
        玩家根本没有周旋空间。
        """
        if player is not None and player.alive:
            same_col = abs(player.rect.centerx - self.rect.centerx) < TANK_SIZE
            same_row = abs(player.rect.centery - self.rect.centery) < TANK_SIZE
            if same_col and self.direction in (UP, DOWN):
                return True
            if same_row and self.direction in (LEFT, RIGHT):
                return True
        if abs(base_rect.centerx - self.rect.centerx) < TANK_SIZE and \
                self.direction == DOWN and self.rect.centery > base_rect.top - 240:
            return random.random() < 0.35
        return random.random() < 0.012


# ==========================================================================
# 特效
# ==========================================================================
class Explosion:
    """爆炸特效：外圈冲击波 + 若干飞散火星。"""

    def __init__(self, center, size=48, duration=0.45):
        self.center = center
        self.size = size
        self.duration = duration
        self.elapsed = 0.0
        self.alive = True
        self.sparks = []
        for _ in range(int(size / 4) + 6):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(size * 0.6, size * 1.9)
            self.sparks.append([math.cos(angle) * speed,
                                math.sin(angle) * speed,
                                random.uniform(2, 4)])

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.alive = False

    def draw(self, surf):
        t = min(1.0, self.elapsed / self.duration)
        cx, cy = self.center

        radius = int(self.size * (0.25 + 0.75 * t))
        ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 190, 90, int(180 * (1 - t))),
                           (radius + 2, radius + 2), radius, max(2, int(6 * (1 - t))))
        pygame.draw.circle(ring, (255, 240, 200, int(220 * (1 - t) ** 2)),
                           (radius + 2, radius + 2), int(radius * 0.5))
        surf.blit(ring, ring.get_rect(center=(cx, cy)))

        for vx, vy, r in self.sparks:
            px = cx + vx * t
            py = cy + vy * t
            size = max(1, int(r * (1 - t)))
            pygame.draw.circle(surf, (255, 210, 120), (int(px), int(py)), size)


class FloatingText:
    """击毁敌人时向上飘出的得分文字。"""

    def __init__(self, center, text, color=C_ACCENT, duration=0.9):
        self.x, self.y = center
        self.text = text
        self.color = color
        self.duration = duration
        self.elapsed = 0.0
        self.alive = True

    def update(self, dt):
        self.elapsed += dt
        self.y -= 26 * dt
        if self.elapsed >= self.duration:
            self.alive = False

    def draw(self, surf):
        t = min(1.0, self.elapsed / self.duration)
        font = assets.get_font(18, bold=True)
        img = font.render(self.text, True, self.color)
        img.set_alpha(int(255 * (1 - t)))
        surf.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
