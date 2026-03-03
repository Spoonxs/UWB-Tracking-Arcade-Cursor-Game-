#!/usr/bin/env python3
"""
Send simulated 1-tag or 2-tag UWB-like UDP data to bridge.py.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Simulate UWB tag packets over UDP")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--tags", type=int, choices=[1, 2], default=1)
    p.add_argument("--hz", type=float, default=20.0)
    p.add_argument("--uwb-x-max", type=float, default=4.0)
    p.add_argument("--uwb-y-max", type=float, default=3.0)
    return p


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def main():
    args = build_parser().parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dt = 1.0 / max(1.0, args.hz)

    print(
        f"[sim] sending {args.tags} tag(s) to udp://{args.host}:{args.port} at {args.hz:.1f} Hz"
    )
    t0 = time.time()
    while True:
        t = time.time() - t0
        tags = []

        x1 = (math.sin(t * 0.8) * 0.45 + 0.5) * args.uwb_x_max
        y1 = (math.cos(t * 1.2) * 0.45 + 0.5) * args.uwb_y_max
        tags.append({"id": 1, "x": clamp(x1, 0.0, args.uwb_x_max), "y": clamp(y1, 0.0, args.uwb_y_max)})

        if args.tags == 2:
            x2 = (math.sin(t * 0.9 + 1.6) * 0.45 + 0.5) * args.uwb_x_max
            y2 = (math.cos(t * 1.1 + 0.8) * 0.45 + 0.5) * args.uwb_y_max
            tags.append({"id": 2, "x": clamp(x2, 0.0, args.uwb_x_max), "y": clamp(y2, 0.0, args.uwb_y_max)})

        payload = json.dumps({"tags": tags}).encode("utf-8")
        sock.sendto(payload, (args.host, args.port))
        time.sleep(dt)


if __name__ == "__main__":
    main()
