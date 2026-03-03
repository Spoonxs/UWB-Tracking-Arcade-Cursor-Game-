#!/usr/bin/env python3
"""
Read Arduino/ESP32 serial output and forward cursor-game-compatible UDP packets.

Accepted serial line formats:
1) Solved coordinates JSON:
   {"id":1,"x":1.23,"y":2.10}
2) Solved coordinates JSON list:
   {"tags":[{"id":1,"x":1.2,"y":2.1},{"id":2,"x":2.4,"y":1.7}]}
3) Anchor-distance JSON (solved here via multilateration):
   {"tag":"T1","anchors":[{"id":"A1","distance":1.23},{"id":"A2","distance":2.12}]}
4) Solved coordinates CSV:
   1,1.23,2.10
5) Solved coordinates key/value:
   id=1 x=1.23 y=2.10
6) Anchor-distance key/value fallback:
   tag=T1 A1=1.23 A2=2.12 A3=1.75 ...

Output UDP packet shape:
{"tags":[{"id":1,"x":1.23,"y":2.10}]}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import re
import socket
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


try:
    import serial  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pyserial is required. Install with: python3 -m pip install --user pyserial"
    ) from exc


RE_ID = re.compile(r"(?:\bid\b|\btag\b)\s*[:=]\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
RE_X = re.compile(r"\bx\b\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
RE_Y = re.compile(r"\by\b\s*[:=]\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
RE_ANCHOR_PAIR = re.compile(r"\b([A-Za-z][A-Za-z0-9_-]*\d+)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)")

# Default 6-anchor layout mapped to game-space meters (x:0..4, y:0..3).
DEFAULT_ANCHOR_POSITIONS: Dict[str, tuple[float, float]] = {
    "A1": (0.0, 0.0),
    "A2": (2.0, 0.0),
    "A3": (4.0, 0.0),
    "A4": (4.0, 3.0),
    "A5": (2.0, 3.0),
    "A6": (0.0, 3.0),
}


@dataclass
class Packet:
    port: str
    tags: List[Dict[str, float]]
    raw: str


def parse_tag_id(value, default_id: Optional[int]) -> Optional[int]:
    if value is None:
        return default_id

    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip()
    if not s:
        return default_id

    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)

    m = re.match(r"^[Tt](\d+)$", s)
    if m:
        return int(m.group(1))

    return default_id


def normalize_anchor_id(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None

    if s.startswith("ANCHOR"):
        s = s[6:]
        s = s.lstrip("_-")

    m = re.match(r"^([A-Z]?)(\d+)$", s)
    if m:
        prefix = m.group(1) or "A"
        return f"{prefix}{int(m.group(2))}"

    m2 = re.match(r"^([A-Z][A-Z0-9_-]*?)(\d+)$", s)
    if m2:
        return f"{m2.group(1)}{int(m2.group(2))}"
    return s


def to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_tag(item: dict, default_id: Optional[int]) -> Optional[Dict[str, float]]:
    if not isinstance(item, dict):
        return None

    tag_id = parse_tag_id(
        item.get("id", item.get("tag", item.get("tagId", item.get("tag_id")))),
        default_id,
    )
    x = to_float(item.get("x", item.get("posX", item.get("pos_x"))))
    y = to_float(item.get("y", item.get("posY", item.get("pos_y"))))

    if tag_id is None or x is None or y is None:
        return None

    return {"id": int(tag_id), "x": x, "y": y}


def parse_anchor_positions_spec(spec: str) -> Dict[str, tuple[float, float]]:
    out: Dict[str, tuple[float, float]] = {}
    if not spec.strip():
        return out

    chunks = [chunk.strip() for chunk in spec.split(";") if chunk.strip()]
    for chunk in chunks:
        m = re.match(r"^([^:=\s]+)\s*[:=]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$", chunk)
        if not m:
            raise ValueError(
                f"Invalid anchor spec chunk '{chunk}'. Expected format like A1:0,0;A2:4,0"
            )
        anchor_id = normalize_anchor_id(m.group(1))
        if not anchor_id:
            raise ValueError(f"Invalid anchor id in chunk '{chunk}'")
        out[anchor_id] = (float(m.group(2)), float(m.group(3)))
    return out


def parse_anchor_positions_file(path: str) -> Dict[str, tuple[float, float]]:
    if not os.path.isfile(path):
        raise ValueError(f"Anchor file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    out: Dict[str, tuple[float, float]] = {}
    if isinstance(obj, dict):
        for raw_id, raw_pos in obj.items():
            anchor_id = normalize_anchor_id(raw_id)
            if not anchor_id:
                continue
            if isinstance(raw_pos, (list, tuple)) and len(raw_pos) >= 2:
                x = to_float(raw_pos[0])
                y = to_float(raw_pos[1])
            elif isinstance(raw_pos, dict):
                x = to_float(raw_pos.get("x"))
                y = to_float(raw_pos.get("y"))
            else:
                x = None
                y = None
            if x is None or y is None:
                continue
            out[anchor_id] = (x, y)
    elif isinstance(obj, list):
        for item in obj:
            if not isinstance(item, dict):
                continue
            anchor_id = normalize_anchor_id(item.get("id"))
            x = to_float(item.get("x"))
            y = to_float(item.get("y"))
            if not anchor_id or x is None or y is None:
                continue
            out[anchor_id] = (x, y)
    else:
        raise ValueError("Anchor file JSON must be an object or list")
    return out


def extract_anchor_distances(item: dict, distance_max: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not isinstance(item, dict):
        return out

    def maybe_add(anchor_raw, distance_raw) -> None:
        anchor_id = normalize_anchor_id(anchor_raw)
        distance = to_float(distance_raw)
        if not anchor_id or distance is None:
            return
        if distance <= 0.0 or distance > distance_max:
            return
        out[anchor_id] = float(distance)

    anchors_field = item.get("anchors")
    if isinstance(anchors_field, list):
        for entry in anchors_field:
            if not isinstance(entry, dict):
                continue
            maybe_add(entry.get("id"), entry.get("distance", entry.get("dist", entry.get("r"))))
    elif isinstance(anchors_field, dict):
        for key, value in anchors_field.items():
            maybe_add(key, value)

    distances_field = item.get("distances")
    if isinstance(distances_field, dict):
        for key, value in distances_field.items():
            maybe_add(key, value)

    ranges_field = item.get("ranges")
    if isinstance(ranges_field, dict):
        for key, value in ranges_field.items():
            maybe_add(key, value)

    for key, value in item.items():
        anchor_id = normalize_anchor_id(key)
        if not anchor_id:
            continue
        maybe_add(anchor_id, value)

    return out


def solve_position_from_distances(
    distances: Dict[str, float],
    anchor_positions: Dict[str, tuple[float, float]],
) -> Optional[tuple[float, float]]:
    points: List[tuple[float, float, float]] = []
    for anchor_id, distance in distances.items():
        if anchor_id not in anchor_positions:
            continue
        ax, ay = anchor_positions[anchor_id]
        points.append((ax, ay, distance))

    if len(points) < 3:
        return None

    x1, y1, r1 = points[0]
    s_xx = 0.0
    s_xy = 0.0
    s_yy = 0.0
    s_xb = 0.0
    s_yb = 0.0

    for ax, ay, ri in points[1:]:
        a = 2.0 * (ax - x1)
        b = 2.0 * (ay - y1)
        c = (r1 * r1) - (ri * ri) + (ax * ax - x1 * x1) + (ay * ay - y1 * y1)
        s_xx += a * a
        s_xy += a * b
        s_yy += b * b
        s_xb += a * c
        s_yb += b * c

    det = s_xx * s_yy - s_xy * s_xy
    if abs(det) < 1e-8:
        return None

    x = (s_xb * s_yy - s_xy * s_yb) / det
    y = (s_xx * s_yb - s_xy * s_xb) / det
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def normalize_or_solve_tag(
    item: dict,
    default_id: Optional[int],
    anchor_positions: Dict[str, tuple[float, float]],
    min_anchors: int,
    distance_max: float,
) -> Optional[Dict[str, float]]:
    direct = normalize_tag(item, default_id)
    if direct:
        return direct

    tag_id = parse_tag_id(
        item.get("id", item.get("tag", item.get("tagId", item.get("tag_id")))),
        default_id,
    )
    if tag_id is None:
        return None

    distances = extract_anchor_distances(item, distance_max=distance_max)
    if len(distances) < min_anchors:
        return None
    xy = solve_position_from_distances(distances, anchor_positions=anchor_positions)
    if xy is None:
        return None

    return {"id": int(tag_id), "x": float(xy[0]), "y": float(xy[1])}


def parse_line(
    line: str,
    default_id: Optional[int],
    anchor_positions: Dict[str, tuple[float, float]],
    min_anchors: int,
    distance_max: float,
) -> List[Dict[str, float]]:
    s = line.strip()
    if not s:
        return []

    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            obj = None

        if isinstance(obj, dict):
            if isinstance(obj.get("tags"), list):
                tags = []
                for t in obj["tags"]:
                    if not isinstance(t, dict):
                        continue
                    nt = normalize_or_solve_tag(
                        t,
                        default_id=default_id,
                        anchor_positions=anchor_positions,
                        min_anchors=min_anchors,
                        distance_max=distance_max,
                    )
                    if nt:
                        tags.append(nt)
                if tags:
                    return tags

            one = normalize_or_solve_tag(
                obj,
                default_id=default_id,
                anchor_positions=anchor_positions,
                min_anchors=min_anchors,
                distance_max=distance_max,
            )
            if one:
                return [one]

    parts = [p.strip() for p in s.split(",")]
    if len(parts) == 3:
        tid = parse_tag_id(parts[0], default_id)
        x = to_float(parts[1])
        y = to_float(parts[2])
        if tid is not None and x is not None and y is not None:
            return [{"id": int(tid), "x": x, "y": y}]

    x_m = RE_X.search(s)
    y_m = RE_Y.search(s)
    if x_m and y_m:
        id_m = RE_ID.search(s)
        tid = parse_tag_id(id_m.group(1) if id_m else None, default_id)
        if tid is not None:
            x = float(x_m.group(1))
            y = float(y_m.group(1))
            return [{"id": int(tid), "x": x, "y": y}]

    if anchor_positions:
        parsed_distances: Dict[str, float] = {}
        for raw_anchor_id, raw_distance in RE_ANCHOR_PAIR.findall(s):
            anchor_id = normalize_anchor_id(raw_anchor_id)
            distance = to_float(raw_distance)
            if not anchor_id or distance is None:
                continue
            if distance <= 0.0 or distance > distance_max:
                continue
            parsed_distances[anchor_id] = float(distance)

        if len(parsed_distances) >= min_anchors:
            id_m = RE_ID.search(s)
            tid = parse_tag_id(id_m.group(1) if id_m else None, default_id)
            if tid is not None:
                xy = solve_position_from_distances(parsed_distances, anchor_positions=anchor_positions)
                if xy is not None:
                    return [{"id": int(tid), "x": float(xy[0]), "y": float(xy[1])}]

    return []


def apply_transform(
    tags: List[Dict[str, float]],
    x_scale: float,
    y_scale: float,
    x_offset: float,
    y_offset: float,
    x_min: Optional[float],
    x_max: Optional[float],
    y_min: Optional[float],
    y_max: Optional[float],
) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for t in tags:
        x = t["x"] * x_scale + x_offset
        y = t["y"] * y_scale + y_offset

        if x_min is not None:
            x = max(x_min, x)
        if x_max is not None:
            x = min(x_max, x)
        if y_min is not None:
            y = max(y_min, y)
        if y_max is not None:
            y = min(y_max, y)

        out.append({"id": int(t["id"]), "x": float(x), "y": float(y)})
    return out


def parse_id_list(spec: str) -> List[int]:
    if not spec.strip():
        return []
    return [int(x.strip()) for x in spec.split(",") if x.strip()]


def serial_reader(
    port: str,
    baud: int,
    default_id: Optional[int],
    anchor_positions: Dict[str, tuple[float, float]],
    min_anchors: int,
    distance_max: float,
    out_q: "queue.Queue[Packet]",
    stop_event: threading.Event,
):
    ser = serial.Serial(port=port, baudrate=baud, timeout=0.2)
    try:
        while not stop_event.is_set():
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                continue
            tags = parse_line(
                raw,
                default_id=default_id,
                anchor_positions=anchor_positions,
                min_anchors=min_anchors,
                distance_max=distance_max,
            )
            if tags:
                out_q.put(Packet(port=port, tags=tags, raw=raw))
    finally:
        ser.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Forward Arduino serial tag data to UDP bridge")
    p.add_argument("--port", action="append", required=True, help="Serial port (repeat for multiple)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--default-tag-ids", default="1", help="Comma list mapped to --port order")
    p.add_argument("--udp-host", default="127.0.0.1")
    p.add_argument("--udp-port", type=int, default=9000)
    p.add_argument("--hz-limit", type=float, default=20.0, help="Max forwarded packets per second per port")

    p.add_argument("--x-scale", type=float, default=1.0)
    p.add_argument("--y-scale", type=float, default=1.0)
    p.add_argument("--x-offset", type=float, default=0.0)
    p.add_argument("--y-offset", type=float, default=0.0)

    p.add_argument("--x-min", type=float, default=0.0)
    p.add_argument("--x-max", type=float, default=4.0)
    p.add_argument("--y-min", type=float, default=0.0)
    p.add_argument("--y-max", type=float, default=3.0)

    p.add_argument(
        "--anchors",
        default="",
        help="Anchor coordinates as A1:0,0;A2:2,0;A3:4,0;A4:4,3;A5:2,3;A6:0,3",
    )
    p.add_argument("--anchors-file", default="", help="JSON file with anchor coordinate map")
    p.add_argument(
        "--no-default-anchors",
        action="store_true",
        help="Disable built-in A1..A6 layout and only use --anchors/--anchors-file",
    )
    p.add_argument("--min-anchors", type=int, default=3, help="Minimum anchors required to solve position")
    p.add_argument("--distance-max", type=float, default=15.0, help="Drop anchor distances above this (meters)")
    return p


def main():
    args = build_parser().parse_args()
    port_defaults = parse_id_list(args.default_tag_ids)
    min_anchors = max(2, int(args.min_anchors))

    anchor_positions: Dict[str, tuple[float, float]] = {}
    if not args.no_default_anchors:
        anchor_positions.update(DEFAULT_ANCHOR_POSITIONS)

    if args.anchors_file:
        try:
            anchor_positions.update(parse_anchor_positions_file(args.anchors_file))
        except Exception as exc:
            raise SystemExit(f"Invalid --anchors-file: {exc}") from exc

    if args.anchors:
        try:
            anchor_positions.update(parse_anchor_positions_spec(args.anchors))
        except Exception as exc:
            raise SystemExit(f"Invalid --anchors: {exc}") from exc

    out_q: "queue.Queue[Packet]" = queue.Queue(maxsize=2000)
    stop_event = threading.Event()
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    readers = []
    for idx, port in enumerate(args.port):
        default_id = port_defaults[idx] if idx < len(port_defaults) else None
        t = threading.Thread(
            target=serial_reader,
            args=(
                port,
                args.baud,
                default_id,
                anchor_positions,
                min_anchors,
                args.distance_max,
                out_q,
                stop_event,
            ),
            daemon=True,
        )
        t.start()
        readers.append((port, default_id, t))

    print("[serial->udp] running")
    for port, default_id, _ in readers:
        print(f"  port={port} default_tag_id={default_id}")
    print(f"  udp={args.udp_host}:{args.udp_port}")
    if anchor_positions:
        print(f"  anchors={len(anchor_positions)} (min_required={min_anchors})")
        for anchor_id in sorted(anchor_positions.keys()):
            ax, ay = anchor_positions[anchor_id]
            print(f"    {anchor_id}=({ax:.3f},{ay:.3f})")
    else:
        print("  anchors=disabled (only direct x,y serial lines will be forwarded)")

    min_dt = 1.0 / max(1.0, args.hz_limit)
    last_send_by_port: Dict[str, float] = {}

    try:
        while True:
            pkt = out_q.get(timeout=0.5)
            now = time.time()
            prev = last_send_by_port.get(pkt.port, 0.0)
            if now - prev < min_dt:
                continue

            tags = apply_transform(
                pkt.tags,
                x_scale=args.x_scale,
                y_scale=args.y_scale,
                x_offset=args.x_offset,
                y_offset=args.y_offset,
                x_min=args.x_min,
                x_max=args.x_max,
                y_min=args.y_min,
                y_max=args.y_max,
            )
            if not tags:
                continue

            payload = json.dumps({"tags": tags}).encode("utf-8")
            udp_sock.sendto(payload, (args.udp_host, args.udp_port))
            last_send_by_port[pkt.port] = now
            print(f"[forwarded] {pkt.port} -> {payload.decode('utf-8')}")
    except KeyboardInterrupt:
        print("\n[serial->udp] stopped")
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
