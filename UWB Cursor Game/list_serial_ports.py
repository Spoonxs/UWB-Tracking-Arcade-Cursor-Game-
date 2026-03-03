#!/usr/bin/env python3
from __future__ import annotations

try:
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit(
        "pyserial is required. Install with: python3 -m pip install --user pyserial"
    ) from exc

ports = list(list_ports.comports())
if not ports:
    print("No serial ports found.")
else:
    for p in ports:
        print(f"{p.device} | {p.description} | hwid={p.hwid}")
