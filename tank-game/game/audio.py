# -*- coding: utf-8 -*-
"""程序合成音效。

不依赖任何外部音频文件：直接用 array 生成 16 位单声道 PCM 波形交给
pygame.mixer 播放。若运行环境没有声卡（例如服务器 / 无声设备），
所有接口自动降级为静音，不影响游戏运行。
"""

import math
import random
from array import array

import pygame

SAMPLE_RATE = 22050

_enabled = False
_sounds = {}


def _clamp16(v):
    return max(-32767, min(32767, int(v)))


def _make_sound(samples):
    """把 int16 序列包装成 pygame.mixer.Sound。"""
    return pygame.mixer.Sound(buffer=array("h", samples).tobytes())


def _tone(freq_start, freq_end, ms, volume=0.35, wave="square", decay=True):
    """生成一段扫频音（freq_start -> freq_end）。"""
    n = int(SAMPLE_RATE * ms / 1000)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n if n else 0.0
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / SAMPLE_RATE
        if wave == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "saw":
            v = 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
        else:
            v = math.sin(phase)
        env = (1.0 - t) if decay else 1.0
        out.append(_clamp16(v * volume * env * 32767))
    return out


def _noise(ms, volume=0.4, decay=True, low_pass=0.35):
    """生成一段带低通的噪声，用来做爆炸声。"""
    n = int(SAMPLE_RATE * ms / 1000)
    out = []
    last = 0.0
    for i in range(n):
        t = i / n if n else 0.0
        raw = random.uniform(-1.0, 1.0)
        last = last + (raw - last) * low_pass      # 一阶低通，声音更“闷”
        env = (1.0 - t) ** 2 if decay else 1.0
        out.append(_clamp16(last * volume * env * 32767))
    return out


def _mix(*tracks):
    """把多段波形按最长长度叠加。"""
    length = max(len(t) for t in tracks)
    out = [0] * length
    for track in tracks:
        for i, v in enumerate(track):
            out[i] = _clamp16(out[i] + v)
    return out


def init():
    """初始化混音器并合成全部音效。失败则静音降级。"""
    global _enabled
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        _sounds["shoot"] = _make_sound(_tone(880, 220, 90, 0.28, "square"))
        _sounds["enemy_shoot"] = _make_sound(_tone(520, 160, 90, 0.16, "square"))
        _sounds["hit_brick"] = _make_sound(_mix(_noise(70, 0.30),
                                                _tone(300, 120, 70, 0.14, "saw")))
        _sounds["hit_steel"] = _make_sound(_tone(1400, 900, 60, 0.22, "square"))
        _sounds["explode"] = _make_sound(_mix(_noise(380, 0.55),
                                              _tone(180, 40, 380, 0.30, "saw")))
        _sounds["player_die"] = _make_sound(_mix(_noise(600, 0.55),
                                                 _tone(320, 30, 600, 0.35, "saw")))
        _sounds["spawn"] = _make_sound(_tone(220, 660, 180, 0.20, "sine"))
        _sounds["win"] = _make_sound(_mix(_tone(523, 523, 140, 0.22, "square", False),
                                          _tone(659, 784, 320, 0.22, "square")))
        _sounds["lose"] = _make_sound(_tone(392, 98, 700, 0.28, "saw"))
        _enabled = True
    except Exception:                      # 没有声卡 / 驱动不可用时静音运行
        _enabled = False


def play(name):
    """播放音效，未初始化成功时静默忽略。"""
    if not _enabled:
        return
    snd = _sounds.get(name)
    if snd is not None:
        try:
            snd.play()
        except Exception:
            pass


def is_enabled():
    return _enabled
