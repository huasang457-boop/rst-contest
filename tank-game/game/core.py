# -*- coding: utf-8 -*-
"""游戏主体：状态机、主循环、碰撞判定与胜负判定。

状态流转：
    menu ──空格──> playing ──P──> paused ──P──> playing
                      │
                      ├── 敌军全灭 ──> win
                      └── 基地被毁 / 生命耗尽 ──> lose
    win / lose ──R──> playing（重新开始）
"""

import os
import random
import time

import pygame

from . import assets, audio
from .background import make_campus_background
from .entities import PlayerTank, EnemyTank, Explosion, FloatingText
from .hud import Hud
from .level import Level
from .settings import (WIN_W, WIN_H, FIELD_X, FIELD_Y, FIELD_W, FIELD_H, FPS,
                       TITLE, TANK_SIZE, UP, RIGHT, DOWN, LEFT, SIDE_PLAYER,
                       PLAYER_LIVES, PLAYER_SPEED, PLAYER_BULLET_SPEED,
                       PLAYER_RELOAD, PLAYER_MAX_BULLETS, TOTAL_ENEMIES,
                       MAX_ALIVE_ENEMIES, ENEMY_SPAWN_INTERVAL, RESPAWN_PROTECT,
                       PLAYER_RESPAWN_DELAY, SCORE_PER_ENEMY,
                       C_BG, C_PANEL_LINE)

# 按键 -> 方向
MOVE_KEYS = {
    pygame.K_w: UP, pygame.K_UP: UP,
    pygame.K_s: DOWN, pygame.K_DOWN: DOWN,
    pygame.K_a: LEFT, pygame.K_LEFT: LEFT,
    pygame.K_d: RIGHT, pygame.K_RIGHT: RIGHT,
}
FIRE_KEYS = (pygame.K_SPACE, pygame.K_j)


class Game:
    """一局游戏的全部状态。"""

    def __init__(self, screen):
        self.screen = screen
        self.field = pygame.Surface((FIELD_W, FIELD_H)).convert()
        self.background = make_campus_background(FIELD_W, FIELD_H)
        self.hud = Hud()
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "menu"
        self.autopilot = None          # 演示模式下由脚本接管操作
        self.reset()

    # ==================================================================
    # 初始化 / 重开
    # ==================================================================
    def reset(self):
        self.level = Level()
        self.initials_total = self.level.initials_remaining()

        self.player = None
        self.enemies = []
        self.bullets = []
        self.effects = []

        self.score = 0
        self.killed = 0
        self.lives = PLAYER_LIVES
        self.spawn_timer = 0.6
        self.respawn_timer = 0.0
        self.spawn_index = 0
        self.water_frame = 0
        self.water_timer = 0.0

        self.pending_enemies = self._make_enemy_queue()
        self._spawn_player()

    @staticmethod
    def _make_enemy_queue():
        """生成本关敌人出场顺序：普通兵为主，穿插快速与装甲。"""
        queue = (["normal"] * 6) + (["fast"] * 4) + (["armor"] * 2)
        random.shuffle(queue)
        queue.insert(0, "normal")          # 第一个固定普通兵，给玩家缓冲
        return queue[:TOTAL_ENEMIES]

    def _spawn_player(self):
        x, y = self.level.player_spawn
        self.player = PlayerTank(x, y, PLAYER_SPEED, PLAYER_BULLET_SPEED,
                                 PLAYER_RELOAD)
        self.player.shield_time = RESPAWN_PROTECT
        audio.play("spawn")

    # ==================================================================
    # 事件
    # ==================================================================
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type != pygame.KEYDOWN:
            return

        key = event.key
        if key == pygame.K_ESCAPE:
            if self.state == "playing":
                self.state = "paused"
            else:
                self.running = False
        elif key == pygame.K_F1:
            self.save_screenshot()
        elif self.state == "menu":
            if key in FIRE_KEYS or key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.state = "playing"
        elif self.state == "playing":
            if key == pygame.K_p:
                self.state = "paused"
            elif key == pygame.K_r:
                self.reset()
        elif self.state == "paused":
            if key == pygame.K_p:
                self.state = "playing"
            elif key == pygame.K_r:
                self.reset()
                self.state = "playing"
        elif self.state in ("win", "lose"):
            if key == pygame.K_r:
                self.reset()
                self.state = "playing"

    # ==================================================================
    # 更新
    # ==================================================================
    def update(self, dt):
        if self.state != "playing":
            return

        self._update_water(dt)
        self._update_player(dt)
        self._update_enemies(dt)
        self._update_bullets(dt)
        self._update_effects(dt)
        self._spawn_enemies(dt)
        self._check_result()

    def _update_water(self, dt):
        self.water_timer += dt
        if self.water_timer >= 0.45:
            self.water_timer = 0.0
            self.water_frame ^= 1

    def _all_tanks(self):
        tanks = [t for t in self.enemies if t.alive]
        if self.player is not None and self.player.alive:
            tanks.append(self.player)
        return tanks

    # ---------------- 玩家 ----------------
    def _read_input(self, dt):
        """读取玩家输入，返回 (方向字典, 是否开火)。

        接了一层是为了让 --demo 演示模式可以用脚本托管操作，
        正常游玩时直接读键盘状态。
        """
        if self.autopilot is not None:
            return self.autopilot.poll(self, dt)

        keys = pygame.key.get_pressed()
        pressed = {UP: False, DOWN: False, LEFT: False, RIGHT: False}
        for key, direction in MOVE_KEYS.items():
            if keys[key]:
                pressed[direction] = True
        return pressed, any(keys[k] for k in FIRE_KEYS)

    def _update_player(self, dt):
        if self.player is None or not self.player.alive:
            if self.respawn_timer > 0:
                self.respawn_timer -= dt
                if self.respawn_timer <= 0 and self.lives > 0:
                    self._spawn_player()
            return

        self.player.update_timers(dt)

        pressed, fire = self._read_input(dt)
        others = [t for t in self.enemies if t.alive]
        self.player.handle_input(pressed, self.level, others, dt)

        # 开火：允许按住连发，受装弹时间与同屏弹数限制
        if fire and self.player.can_fire():
            alive_own = sum(1 for b in self.bullets
                            if b.alive and b.side == SIDE_PLAYER)
            if alive_own < PLAYER_MAX_BULLETS:
                self.bullets.append(self.player.make_bullet())
                self.player.reload_time = self.player.reload_interval
                audio.play("shoot")

    # ---------------- 敌人 ----------------
    def _update_enemies(self, dt):
        others = self._all_tanks()
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.update_timers(dt)
            bullet = enemy.think(dt, self.level, others, self.player,
                                 self.level.base_rect)
            if bullet is not None:
                self.bullets.append(bullet)
                audio.play("enemy_shoot")
        self.enemies = [e for e in self.enemies if e.alive]

    def _spawn_enemies(self, dt):
        if not self.pending_enemies:
            return
        self.spawn_timer -= dt
        if self.spawn_timer > 0 or len(self.enemies) >= MAX_ALIVE_ENEMIES:
            return

        # 依次尝试三个出生点，找一个没被占住的
        for i in range(len(self.level.enemy_spawns)):
            idx = (self.spawn_index + i) % len(self.level.enemy_spawns)
            sx, sy = self.level.enemy_spawns[idx]
            rect = pygame.Rect(sx, sy, TANK_SIZE, TANK_SIZE)
            if any(t.rect.colliderect(rect) for t in self._all_tanks()):
                continue
            kind = self.pending_enemies.pop(0)
            enemy = EnemyTank(sx, sy, kind)
            enemy.shield_time = 0.8
            self.enemies.append(enemy)
            self.effects.append(Explosion(rect.center, 40, 0.35))
            self.spawn_index = idx + 1
            self.spawn_timer = ENEMY_SPAWN_INTERVAL
            audio.play("spawn")
            return
        self.spawn_timer = 0.4          # 出生点都被占，稍后再试

    # ---------------- 子弹 ----------------
    def _update_bullets(self, dt):
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            material = bullet.update(self.level)
            if material == "brick":
                self.effects.append(Explosion(bullet.rect.center, 26, 0.25))
                audio.play("hit_brick")
                continue
            if material == "steel":
                self.effects.append(Explosion(bullet.rect.center, 18, 0.18))
                audio.play("hit_steel")
                continue
            if material == "base":
                self.effects.append(Explosion(self.level.base_rect.center, 92, 0.8))
                audio.play("explode")
                continue

            self._bullet_vs_tanks(bullet)

        self._bullets_vs_bullets()
        self.bullets = [b for b in self.bullets if b.alive]

    def _bullet_vs_tanks(self, bullet):
        if bullet.side == SIDE_PLAYER:
            for enemy in self.enemies:
                if enemy.alive and bullet.rect.colliderect(enemy.rect):
                    bullet.alive = False
                    if enemy.take_damage(bullet.power):
                        self._on_enemy_killed(enemy)
                    else:
                        self.effects.append(Explosion(bullet.rect.center, 22, 0.2))
                        audio.play("hit_steel")
                    return
        else:
            player = self.player
            if player is not None and player.alive and \
                    bullet.rect.colliderect(player.rect):
                bullet.alive = False
                if player.shield_time > 0:
                    self.effects.append(Explosion(bullet.rect.center, 24, 0.2))
                    audio.play("hit_steel")
                    return
                if player.take_damage(1):
                    self._on_player_killed()

    def _bullets_vs_bullets(self):
        """敌我炮弹相撞则相互抵消。"""
        for i, a in enumerate(self.bullets):
            if not a.alive:
                continue
            for b in self.bullets[i + 1:]:
                if b.alive and a.side != b.side and a.rect.colliderect(b.rect):
                    a.alive = b.alive = False
                    self.effects.append(Explosion(a.rect.center, 20, 0.18))
                    audio.play("hit_steel")
                    break

    # ---------------- 击毁结算 ----------------
    def _on_enemy_killed(self, enemy):
        gain = SCORE_PER_ENEMY.get(enemy.kind, 100)
        self.score += gain
        self.killed += 1
        self.effects.append(Explosion(enemy.rect.center, 58, 0.5))
        self.effects.append(FloatingText(enemy.rect.center, "+%d" % gain))
        audio.play("explode")

    def _on_player_killed(self):
        self.lives -= 1
        self.effects.append(Explosion(self.player.rect.center, 72, 0.6))
        audio.play("player_die")
        if self.lives > 0:
            self.respawn_timer = PLAYER_RESPAWN_DELAY

    # ---------------- 特效 ----------------
    def _update_effects(self, dt):
        for fx in self.effects:
            fx.update(dt)
        self.effects = [fx for fx in self.effects if fx.alive]

    # ---------------- 胜负 ----------------
    def _check_result(self):
        if self.level.base_destroyed:
            self._finish("lose")
            return
        if self.lives <= 0 and (self.player is None or not self.player.alive):
            self._finish("lose")
            return
        if not self.pending_enemies and not self.enemies:
            self._finish("win")

    def _finish(self, state):
        if self.state == state:
            return
        self.state = state
        audio.play("win" if state == "win" else "lose")

    # ==================================================================
    # 绘制
    # ==================================================================
    def draw(self):
        self.screen.fill(C_BG)

        # 战场
        self.field.blit(self.background, (0, 0))
        self.level.draw_ground(self.field, (0, 0), self.water_frame)
        for enemy in self.enemies:
            enemy.draw(self.field)
        if self.player is not None:
            self.player.draw(self.field)
        for bullet in self.bullets:
            bullet.draw(self.field)
        self.level.draw_overlay(self.field)          # 树林画在坦克之上
        for fx in self.effects:
            fx.draw(self.field)

        self.screen.blit(self.field, (FIELD_X, FIELD_Y))
        pygame.draw.rect(self.screen, C_PANEL_LINE,
                         pygame.Rect(FIELD_X - 2, FIELD_Y - 2,
                                     FIELD_W + 4, FIELD_H + 4), 2,
                         border_radius=4)

        # 信息栏与状态层
        self.hud.draw_panel(self.screen, self)
        self.hud.draw_overlay(self.screen, self)

    # ==================================================================
    # 工具
    # ==================================================================
    def enemies_left(self):
        """还没打完的敌人数（未出场 + 场上存活）。"""
        return len(self.pending_enemies) + len(self.enemies)

    def save_screenshot(self, path=None):
        """F1 保存当前画面，方便录制演示素材。"""
        folder = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "screenshots")
        os.makedirs(folder, exist_ok=True)
        if path is None:
            path = os.path.join(folder, "shot_%s.png" % time.strftime("%H%M%S"))
        pygame.image.save(self.screen, path)
        return path

    # ==================================================================
    # 主循环
    # ==================================================================
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)                 # 防止窗口卡顿导致穿墙
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()


def create_screen():
    """创建窗口。"""
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(TITLE)
    try:                                      # 用程序生成的图标当窗口图标
        icon = assets.get_tank("player", UP, 32)
        pygame.display.set_icon(icon)
    except Exception:
        pass
    return screen
