@echo off
title 坦克大战 · WZQ
cd /d "%~dp0"

echo 正在检查运行环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 没有检测到 Python，请先安装 Python 3.8 或更高版本。
    echo        下载地址： https://www.python.org/downloads/
    echo        安装时记得勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

python -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo 首次运行，正在安装依赖 pygame ...
    python -m pip install pygame
)

echo 启动游戏...
python main.py
if errorlevel 1 pause
