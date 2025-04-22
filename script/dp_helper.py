#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Only the helper that rebuilds Tuya’s DP‑catalogue string
"""
def tuya_dp_catalogue(frames):
    """
    frames – iterable with the *raw payload bytes* (b'…') in arrival order
    returns the decoded ASCII catalogue string
    """
    buf = bytearray()
    for raw in frames:
        cmd = raw[0]
        if cmd == 0x31:              # 16‑byte block
            buf.extend(raw[3:])      # strip 3‑byte header
        elif cmd == 0x24:            # 2‑byte continuation
            for b in raw[1:3]:
                if b != 0xFF:        # 0xFF = “no‑char”
                    buf.append(b - 0x10)
    return buf.decode("ascii")
