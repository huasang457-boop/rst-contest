# -*- coding: utf-8 -*-
"""坦克大战 · WZQ —— 程序入口。

运行：
    python main.py                    正常游玩
    python main.py --demo             自动演示（AI 托管玩家，用于录屏）
    python main.py --shot out.png     跑若干帧后保存一张截图（可配 --headless）

作者：WZQ
"""

import argparse
import os
import random
import sys

# 引入 pygame 前先关掉启动横幅，控制台更干净
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="坦克大战 · WZQ")
    parser.add_argument("--demo", action="store_true",
                        help="自动演示模式：由脚本操控玩家坦克")
    parser.add_argument("--shot", metavar="PATH", default=None,
                        help="跑完 --frames 帧后保存截图到指定路径并退出")
    parser.add_argument("--frames", type=int, default=300,
                        help="配合 --shot 使用，先空跑多少帧（默认 300）")
    parser.add_argument("--state", default=None,
                        choices=["menu", "playing", "paused", "win", "lose"],
                        help="配合 --shot 使用，指定截图时的界面状态")
    parser.add_argument("--headless", action="store_true",
                        help="无窗口运行（配合 --shot 在无显示器环境下截图）")
    parser.add_argument("--mute", action="store_true", help="静音运行")
    parser.add_argument("--seed", type=int, default=None, help="固定随机种子")
    return parser.parse_args(argv)


class Autopilot:
    """演示 / 截图用的简易自动操作：朝敌人靠近并开火，卡住就换方向。"""

    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.timer = 0.0
        self.direction = None

    def poll(self, game, dt):
        from game.settings import UP, DOWN, LEFT, RIGHT

        self.timer -= dt
        player = game.player
        if self.direction is None or self.timer <= 0 or not player.moving:
            target = None
            if game.enemies:
                target = min(game.enemies,
                             key=lambda e: abs(e.rect.centerx - player.rect.centerx) +
                             abs(e.rect.centery - player.rect.centery))
            if target is not None and self.rnd.random() < 0.75:
                dx = target.rect.centerx - player.rect.centerx
                dy = target.rect.centery - player.rect.centery
                if abs(dx) > abs(dy):
                    self.direction = RIGHT if dx > 0 else LEFT
                else:
                    self.direction = DOWN if dy > 0 else UP
            else:
                self.direction = self.rnd.choice([UP, DOWN, LEFT, RIGHT])
            self.timer = self.rnd.uniform(0.35, 1.1)

        pressed = {UP: False, DOWN: False, LEFT: False, RIGHT: False}
        pressed[self.direction] = True
        return pressed, self.rnd.random() < 0.35


def main(argv=None):
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    if args.seed is not None:
        random.seed(args.seed)

    import pygame
    from game import audio
    from game.core import Game, create_screen

    pygame.init()
    if not args.mute and not args.headless:
        audio.init()
    pygame.font.init()

    screen = create_screen()
    game = Game(screen)

    if args.demo or args.shot:
        game.autopilot = Autopilot(args.seed)

    # ---- 截图模式：空跑固定帧数后存图退出 ----
    if args.shot:
        # 先按正常规则跑够帧数，再把界面切到想要的状态截图，
        # 这样胜利 / 失败画面上的数据都是真打出来的。
        game.state = "playing"
        for _ in range(max(1, args.frames)):
            pygame.event.pump()
            game.update(1.0 / 60)
            if game.state in ("win", "lose"):
                break
        if args.state:
            game.state = args.state
        game.draw()
        pygame.display.flip()
        os.makedirs(os.path.dirname(os.path.abspath(args.shot)), exist_ok=True)
        pygame.image.save(screen, args.shot)
        print("截图已保存:", args.shot)
        pygame.quit()
        return 0

    if args.demo:
        game.state = "playing"

    try:
        game.run()
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
