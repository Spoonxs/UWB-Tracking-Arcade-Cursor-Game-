#!/usr/bin/env python3
"""
UDP -> WebSocket bridge for UWB tag data.

Supported UDP payload formats:
1) JSON single tag:
   {"id":1,"x":1.23,"y":2.10}
2) JSON tags list:
   {"tags":[{"id":1,"x":1.2,"y":2.1},{"id":2,"x":2.4,"y":1.7}]}
3) CSV id,x,y:
   1,1.23,2.10
4) CSV x,y,z (xyz mode):
   1.23,2.10,0.85

Broadcast format to browser clients:
{"tags":[{"id":1,"x":1.23,"y":2.10,"ts":1234.56}, ...]}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "websockets is required. Install with: py -m pip install websockets (Windows) or python3 -m pip install websockets"
    ) from exc


@dataclass
class TagPoint:
    id: int
    x: float
    y: float
    ts: float


@dataclass
class BridgeConfig:
    default_tag_id: int
    csv3_mode: str  # auto | idxy | xyz
    x_scale: float
    y_scale: float
    x_offset: float
    y_offset: float
    x_min: Optional[float]
    x_max: Optional[float]
    y_min: Optional[float]
    y_max: Optional[float]
    ema_alpha: float


def parse_tag_id(raw: Any, fallback: Optional[int]) -> Optional[int]:
    if raw is None:
        return fallback
    if isinstance(raw, (int, float)):
        if math.isfinite(float(raw)):
            return int(raw)
        return fallback

    s = str(raw).strip()
    if not s:
        return fallback
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    m = re.fullmatch(r"[Tt](\d+)", s)
    if m:
        return int(m.group(1))
    return fallback


def to_float(raw: Any) -> Optional[float]:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def clamp(v: float, min_v: Optional[float], max_v: Optional[float]) -> float:
    out = v
    if min_v is not None:
        out = max(min_v, out)
    if max_v is not None:
        out = min(max_v, out)
    return out


def transform_point(p: TagPoint, cfg: BridgeConfig) -> Optional[TagPoint]:
    x = p.x * cfg.x_scale + cfg.x_offset
    y = p.y * cfg.y_scale + cfg.y_offset
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    x = clamp(x, cfg.x_min, cfg.x_max)
    y = clamp(y, cfg.y_min, cfg.y_max)
    return TagPoint(id=p.id, x=x, y=y, ts=p.ts)


def from_json_item(item: Any, ts: float, cfg: BridgeConfig) -> Optional[TagPoint]:
    if not isinstance(item, dict):
        return None
    tag_id = parse_tag_id(
        item.get("id", item.get("tagId", item.get("tag_id", item.get("tag")))),
        cfg.default_tag_id,
    )
    if tag_id is None:
        return None

    x = to_float(item.get("x", item.get("posX", item.get("pos_x"))))
    y_raw = item.get("y", item.get("posY", item.get("pos_y")))
    if cfg.csv3_mode == "xyz":
        y_raw = item.get("z", item.get("posZ", item.get("pos_z", y_raw)))
    y = to_float(y_raw)
    if x is None or y is None:
        return None
    return TagPoint(id=tag_id, x=x, y=y, ts=ts)


def parse_csv_three(parts: List[str], ts: float, cfg: BridgeConfig) -> List[TagPoint]:
    a = to_float(parts[0])
    b = to_float(parts[1])
    c = to_float(parts[2])
    id_from_first = parse_tag_id(parts[0], None)

    can_idxy = id_from_first is not None and b is not None and c is not None
    can_xyz = a is not None and b is not None and c is not None

    if cfg.csv3_mode == "idxy":
        if can_idxy:
            return [TagPoint(id=id_from_first, x=b, y=c, ts=ts)]
        return []

    if cfg.csv3_mode == "xyz":
        if can_xyz:
            # x <- packet.x, y <- packet.z ; packet.y is depth/out-of-screen
            return [TagPoint(id=cfg.default_tag_id, x=a, y=c, ts=ts)]
        return []

    # auto mode
    if can_idxy:
        return [TagPoint(id=id_from_first, x=b, y=c, ts=ts)]
    if can_xyz:
        return [TagPoint(id=cfg.default_tag_id, x=a, y=c, ts=ts)]
    return []


def parse_udp_payload(text: str, cfg: BridgeConfig) -> List[TagPoint]:
    now = time.time()

    if text and text[0] == "{":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return []

        if isinstance(obj, dict) and isinstance(obj.get("tags"), list):
            points = [from_json_item(item, now, cfg) for item in obj["tags"]]
            return [p for p in points if p is not None]

        one = from_json_item(obj, now, cfg)
        return [one] if one is not None else []

    parts = [p.strip() for p in text.split(",")]
    if len(parts) == 3:
        return parse_csv_three(parts, now, cfg)
    return []


class UdpBridgeProtocol(asyncio.DatagramProtocol):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler

    def datagram_received(self, data: bytes, _addr):
        self.handler(data)


class BridgeServer:
    def __init__(self, udp_host: str, udp_port: int, ws_host: str, ws_port: int, cfg: BridgeConfig):
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.cfg = cfg
        self.clients: Set[WebSocketServerProtocol] = set()
        self.queue: asyncio.Queue[List[TagPoint]] = asyncio.Queue(maxsize=500)
        self.last_seen: Dict[int, TagPoint] = {}

    def smooth_point(self, point: TagPoint) -> TagPoint:
        alpha = self.cfg.ema_alpha
        if not (0.0 < alpha < 1.0):
            return point
        prev = self.last_seen.get(point.id)
        if prev is None:
            return point
        x = prev.x + (point.x - prev.x) * alpha
        y = prev.y + (point.y - prev.y) * alpha
        return TagPoint(id=point.id, x=x, y=y, ts=point.ts)

    async def run(self):
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: UdpBridgeProtocol(self.on_udp_bytes),
            local_addr=(self.udp_host, self.udp_port),
        )

        ws_server = await websockets.serve(self.ws_handler, self.ws_host, self.ws_port)
        print(f"[bridge.py] UDP listening on {self.udp_host}:{self.udp_port}")
        print(f"[bridge.py] WebSocket on ws://{self.ws_host}:{self.ws_port}")
        print(
            f"[bridge.py] csv-3-mode={self.cfg.csv3_mode} default-tag-id={self.cfg.default_tag_id} "
            f"transform x=(x*{self.cfg.x_scale})+{self.cfg.x_offset} y=(y*{self.cfg.y_scale})+{self.cfg.y_offset} "
            f"ema-alpha={self.cfg.ema_alpha}"
        )
        if self.cfg.csv3_mode == "xyz":
            print("[bridge.py] axis mapping: screen.x<-packet.x, screen.y<-packet.z, packet.y=depth")

        broadcaster = asyncio.create_task(self.broadcast_loop())
        try:
            await asyncio.Future()
        finally:
            broadcaster.cancel()
            ws_server.close()
            await ws_server.wait_closed()

    def on_udp_bytes(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="ignore").strip()
            if not text:
                return
            points = parse_udp_payload(text, self.cfg)
            if not points:
                return

            transformed: List[TagPoint] = []
            for p in points:
                tp = transform_point(p, self.cfg)
                if tp is not None:
                    transformed.append(self.smooth_point(tp))
            if not transformed:
                return

            for p in transformed:
                self.last_seen[p.id] = p

            if self.queue.full():
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            self.queue.put_nowait(transformed)
        except Exception:
            return

    async def ws_handler(self, websocket: WebSocketServerProtocol):
        self.clients.add(websocket)
        try:
            if self.last_seen:
                await websocket.send(json.dumps({"tags": [asdict(p) for p in self.last_seen.values()]}))
            async for _ in websocket:
                pass
        finally:
            self.clients.discard(websocket)

    async def broadcast_loop(self):
        while True:
            points = await self.queue.get()
            if not self.clients:
                continue
            payload = json.dumps({"tags": [asdict(p) for p in points]})
            stale: List[WebSocketServerProtocol] = []
            for client in self.clients:
                try:
                    await client.send(payload)
                except Exception:
                    stale.append(client)
            for dead in stale:
                self.clients.discard(dead)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UWB UDP -> WebSocket bridge (Python)")
    p.add_argument("--udp-host", default="0.0.0.0")
    p.add_argument("--udp-port", type=int, default=9000)
    p.add_argument("--ws-host", default="127.0.0.1")
    p.add_argument("--ws-port", type=int, default=8765)
    p.add_argument("--default-tag-id", type=int, default=1)
    p.add_argument("--csv-3-mode", choices=["auto", "idxy", "xyz"], default="xyz")
    p.add_argument("--x-scale", type=float, default=1.0)
    p.add_argument("--y-scale", type=float, default=1.0)
    p.add_argument("--x-offset", type=float, default=0.0)
    p.add_argument("--y-offset", type=float, default=0.0)
    p.add_argument("--x-min", type=float, default=None)
    p.add_argument("--x-max", type=float, default=None)
    p.add_argument("--y-min", type=float, default=None)
    p.add_argument("--y-max", type=float, default=None)
    p.add_argument("--ema-alpha", type=float, default=0.35, help="0..1 smoothing factor; 1 disables smoothing")
    return p


def main():
    args = build_parser().parse_args()
    cfg = BridgeConfig(
        default_tag_id=int(args.default_tag_id),
        csv3_mode=str(args.csv_3_mode),
        x_scale=float(args.x_scale),
        y_scale=float(args.y_scale),
        x_offset=float(args.x_offset),
        y_offset=float(args.y_offset),
        x_min=args.x_min,
        x_max=args.x_max,
        y_min=args.y_min,
        y_max=args.y_max,
        ema_alpha=float(args.ema_alpha),
    )
    server = BridgeServer(
        udp_host=args.udp_host,
        udp_port=int(args.udp_port),
        ws_host=args.ws_host,
        ws_port=int(args.ws_port),
        cfg=cfg,
    )
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
