#!/usr/bin/env python3
"""
Decode the “DP‑catalogue” that Tuya squeezes into a 0x31 + 0x24 command burst.

Usage examples
--------------

# a single 0x31 frame *and* the two 0x24 continuation frames
python dp_catalogue.py \
    091c3175686f7074766665646f6a7161767039 \
    0963248272 \
    091e2484ff

# copy‑paste directly from ZHA debug logs (they’re already hex):
python dp_catalogue.py 09 1e 31 00 23 01 01 07 75 68 ...

If you only give the first (0x31) frame you’ll mostly see control bytes –
the real printable part comes from the 0x24 chunks!
"""

from __future__ import annotations
import argparse
import sys
from typing import List


def tuya_dp_catalogue(frames: List[bytes]) -> bytes:
    """
    frames – raw ZCL *payloads* (as bytes, **not** the whole Zigbee packet)

    Returns the raw, unfiltered byte catalogue (ASCII once printable).
    """
    buf = bytearray()

    for p in frames:
        if len(p) < 3:                                 # too short to matter
            continue

        cmd = p[2]                                     # ZCL command id
        if cmd == 0x31:                                # big 16‑byte block
            # strip ZCL header (frame‑ctl + TSN + cmd id  -> 3 bytes)
            # plus the status byte that follows it  -> total 4
            buf.extend(p[4:])

        elif cmd == 0x24:                              # 2‑byte continuation
            # payload layout is   [cmd][TSN][hi][lo]
            if len(p) < 5:
                continue
            for b in (p[3], p[4]):                     # two ASCII halves
                if b != 0xFF:                          # 0xFF = padding
                    buf.append(b - 0x10)               # Tuya’s “‑0x10” quirk

        # ignore everything else

    return bytes(buf)


def nice_ascii(b: bytes) -> str:
    """Return printable ASCII, replacing control bytes by dots."""
    return ''.join(chr(x) if 0x20 <= x < 0x7F else '.' for x in b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "frames",
        metavar="FRAME",
        nargs="+",
        help=(
            "hex strings of the *payload* part of ZCL frames "
            "(strip the outer 'Serialized[b\"...\"]'). "
            "You can paste several – order doesn’t matter."
        ),
    )
    args = ap.parse_args()

    # collect raw‑bytes frames ---------------------------------------------
    raw_frames: List[bytes] = []
    for item in args.frames:
        item = item.replace("0x", "").replace(" ", "").replace("\\x", "")
        if len(item) % 2:                              # must be full bytes
            print(f"⚠︎  odd number of hex digits in ‘{item}’ – skipped", file=sys.stderr)
            continue
        try:
            raw_frames.append(bytes.fromhex(item))
        except ValueError as exc:
            print(f"⚠︎  cannot decode ‘{item}’: {exc} – skipped", file=sys.stderr)

    if not raw_frames:
        sys.exit("No valid frames supplied.")

    cat = tuya_dp_catalogue(raw_frames)
    if not cat:
        sys.exit("Nothing decoded – did you include the 0x24 continuation frames?")

    # ----------------------------------------------------------------------
    print("ASCII catalogue :", nice_ascii(cat) or "<no printable characters>")
    print("raw bytes       :", cat.hex())


if __name__ == "__main__":
    main()
