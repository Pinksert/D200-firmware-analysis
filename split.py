#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nikon D200 官方固件拆分 / 校验脚本
==================================

尼康 D200 的官方升级文件（固件版本 2.01）下载后是一个整体二进制，
内部由两段组成，每段末尾 2 字节是 CRC16/XMODEM 校验和：

    [ A 段 256 KB + 2 B CRC ]  [ B 段 3.75 MB + 2 B CRC ]

其中：
    A 段 = 协处理器固件（IO 协处理，基址 0x80000）
    B 段 = 主控固件（UI + 影像处理，富士通 FR 内核，基址 0x40000）

本脚本把整体文件 D200_0201.bin 拆回 A2000201.bin / B2000201.bin，
并校验两段末尾的 CRC16/XMODEM 是否正确。也可只做校验（--check）。

用法：
    python3 split.py            # 拆分 + 校验，写出 A/B 两段
    python3 split.py --check    # 仅校验已存在的 A/B，不写出
    python3 split.py --src X.bin --outdir ./

CRC16/XMODEM: poly=0x1021, init=0x0000, 不反转, 大端存于末 2 字节。
"""
import os
import sys
import struct
import argparse

# ---- 已知尺寸（来自实测，段大小已含末尾 2 字节 CRC）----
A_TOTAL  = 256 * 1024 + 2            # 256 KB 载荷 + 2 B CRC  -> 262146
B_TOTAL  = 3 * 1024 * 1024 + 768 * 1024   # 3.75 MB（含 2 B CRC）-> 3932160

DEFAULT_SRC = "D200_0201.bin"


def crc16_xmodem(data: bytes) -> int:
    """CRC-16/XMODEM: poly=0x1021, init=0x0000, 大端输出。"""
    crc = 0x0000
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def verify(name: str, body: bytes, tail: bytes) -> bool:
    calc = crc16_xmodem(body)
    stored = struct.unpack(">H", tail)[0]
    ok = (calc == stored)
    print(f"  {name}: 载荷 {len(body):>8} B | CRC 计算=0x{calc:04X} 文件=0x{stored:04X} "
          f"-> {'OK' if ok else 'MISMATCH!'}")
    return ok


def split(src: str, outdir: str) -> bool:
    if not os.path.isfile(src):
        print(f"[错误] 找不到整体固件文件: {src}")
        return False
    data = open(src, "rb").read()
    print(f"读取整体文件 {src}: {len(data)} B")

    if len(data) != A_TOTAL + B_TOTAL:
        print(f"[警告] 整体文件大小 {len(data)} 不等于 "
              f"预期 {A_TOTAL + B_TOTAL}（A {A_TOTAL} + B {B_TOTAL}），"
              f"将按 A={A_TOTAL} 切分，剩余全部视为 B。")

    a = data[:A_TOTAL]
    b = data[A_TOTAL:A_TOTAL + B_TOTAL]
    if len(b) < 2:
        print("[错误] B 段数据不足，文件可能不完整。")
        return False

    a_body, a_tail = a[:-2], a[-2:]
    b_body, b_tail = b[:-2], b[-2:]

    ok = True
    ok &= verify("A 段", a_body, a_tail)
    ok &= verify("B 段", b_body, b_tail)

    if ok and not args.check:
        open(os.path.join(outdir, "A2000201.bin"), "wb").write(a)
        open(os.path.join(outdir, "B2000201.bin"), "wb").write(b)
        print(f"已写出 A2000201.bin ({len(a)} B) 和 B2000201.bin ({len(b)} B) 到 {outdir}/")
    elif args.check:
        print("（仅校验模式，未写出文件）")
    return ok


def main():
    global args
    ap = argparse.ArgumentParser(description="Nikon D200 固件拆分 / 校验")
    ap.add_argument("--src", default=DEFAULT_SRC, help=f"整体固件文件 (默认 {DEFAULT_SRC})")
    ap.add_argument("--outdir", default=".", help="A/B 输出目录 (默认当前目录)")
    ap.add_argument("--check", action="store_true", help="仅校验已存在的 A/B，不拆分写出")
    args = ap.parse_args()

    if args.check:
        a = open("A2000201.bin", "rb").read() if os.path.isfile("A2000201.bin") else b""
        b = open("B2000201.bin", "rb").read() if os.path.isfile("B2000201.bin") else b""
        if not a or not b:
            print("[错误] 校验模式需要已存在的 A2000201.bin / B2000201.bin")
            return 2
        ok = verify("A 段", a[:-2], a[-2:]) & verify("B 段", b[:-2], b[-2:])
        return 0 if ok else 1

    ok = split(args.src, args.outdir)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
