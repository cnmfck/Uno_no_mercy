#!/usr/bin/env sh
# 在此脚本所在目录启动，避免从别的工作目录运行时找不到模块。
cd -- "$(dirname -- "$0")" || exit 1
exec python3 main.py
