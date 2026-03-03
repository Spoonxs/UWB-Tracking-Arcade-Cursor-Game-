#!/usr/bin/env python3
"""
Adapter simulator that reuses movement behavior from the research repo:
external/esp32-uwb-positioning-system/python/uwb_tag_simulator.py

Sends cursor-game-compatible UDP packets:
{"tags":[{"id":1,"x":...,"y":...}, ...]}
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Simulate tag packets using research repo movement model")
    p.add_argument("--repo-path", default="external/esp32-uwb-positioning-system")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--tags", type=int, choices=[1, 2], default=1)
    p.add_argument("--movement", choices=["circle", "random"], default="circle")
    p.add_argument("--hz", type=float, default=20.0)
    return p


def load_simulator_class(repo_path: Path):
    sim_path = repo_path / "python" / "uwb_tag_simulator.py"
    if not sim_path.exists():
        raise FileNotFoundError(f"Simulator not found: {sim_path}")

    spec = importlib.util.spec_from_file_location("research_uwb_tag_simulator", sim_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load simulator module from {sim_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UWBTagSimulator


def step_sim(sim, movement: str):
    if movement == "circle":
        sim.update_position()
    else:
        sim.generate_random_movement()


def to_cursor_game_xy(pos):
    # Research simulator world is 8m x 6m. Cursor game expects 4m x 3m.
    return round(pos[0] / 2.0, 4), round(pos[1] / 2.0, 4)


def main():
    args = build_parser().parse_args()
    repo_path = Path(args.repo_path)

    sim_cls = load_simulator_class(repo_path)
    sim1 = sim_cls()
    sim1.current_pos = [4.0, 3.0]
    sim1.center_pos = [4.0, 3.0]
    sim1.movement_radius = 2.0
    sim1.angle = 0.0
    sim1.speed = 2.0

    sim2 = None
    if args.tags == 2:
        sim2 = sim_cls()
        sim2.current_pos = [3.0, 2.5]
        sim2.center_pos = [3.0, 2.5]
        sim2.movement_radius = 2.2
        sim2.angle = 1.7
        sim2.speed = 1.6

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dt = 1.0 / max(1.0, args.hz)

    print(
        f"[sim-research] tags={args.tags} movement={args.movement} "
        f"udp://{args.host}:{args.port} hz={args.hz:.1f}"
    )

    try:
        while True:
            step_sim(sim1, args.movement)
            x1, y1 = to_cursor_game_xy(sim1.current_pos)
            tags = [{"id": 1, "x": x1, "y": y1}]

            if sim2 is not None:
                step_sim(sim2, args.movement)
                x2, y2 = to_cursor_game_xy(sim2.current_pos)
                tags.append({"id": 2, "x": x2, "y": y2})

            payload = json.dumps({"tags": tags}).encode("utf-8")
            sock.sendto(payload, (args.host, args.port))
            time.sleep(dt)
    except KeyboardInterrupt:
        print("\n[sim-research] stopped")


if __name__ == "__main__":
    main()
