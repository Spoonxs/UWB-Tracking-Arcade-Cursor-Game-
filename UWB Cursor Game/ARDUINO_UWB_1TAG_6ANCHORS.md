# Arduino -> Web Game (1 Tag, 6 Anchors)

## 1) What the game expects
All game pages read this shared stream shape:

```json
{"tags":[{"id":1,"x":1.23,"y":2.10}]}
```

You do **not** need to emit this directly from Arduino.
`serial_to_udp.py` can solve `x,y` from anchor distances.

## 2) Recommended serial output from your tag sketch
Print one JSON line repeatedly (115200 baud):

```json
{"tag":"T1","anchors":[{"id":"A1","distance":1.23},{"id":"A2","distance":2.34},{"id":"A3","distance":1.98},{"id":"A4","distance":2.61},{"id":"A5","distance":1.77},{"id":"A6","distance":2.44}]}
```

Notes:
- `tag` can be `T1` or numeric `1`.
- At least 3 valid anchors are required per line.
- Distances are meters.

## 3) Run stack
Terminal A:
```bash
./run_hardware.sh --tag1 1 --open
```

Terminal B:
```bash
python3 serial_to_udp.py \
  --port /dev/ttyUSB0 \
  --baud 115200 \
  --default-tag-ids 1 \
  --anchors-file anchor_layout_6.json \
  --min-anchors 3
```

On Windows serial port is typically `COM3`, `COM4`, etc.

## 4) Set real anchor coordinates
Edit `anchor_layout_6.json`:

```json
{
  "A1": [0.0, 0.0],
  "A2": [2.0, 0.0],
  "A3": [4.0, 0.0],
  "A4": [4.0, 3.0],
  "A5": [2.0, 3.0],
  "A6": [0.0, 3.0]
}
```

Replace with your measured anchor positions in meters.

## 5) Calibration knobs
- Scale/offset:
  - `--x-scale`, `--y-scale`
  - `--x-offset`, `--y-offset`
- Clamp to game area:
  - `--x-min 0 --x-max 4 --y-min 0 --y-max 3`

These are useful if your physical test area does not map 1:1 to game bounds.

## 6) If your current firmware sends `x,y,z` UDP
Your group visualizer (`CoordsVisualizer2.0.py`) uses 3-value CSV packets.
You can use that stream directly in the game now:

```bash
./run_hardware.sh --tag1 1 --bridge-csv-3-mode xyz --bridge-default-tag-id 1 --open
```

This maps:
- packet `x` -> game `x`
- packet `z` -> game `y` (vertical on screen)
- packet `y` is treated as depth/out-of-screen

For tracking bounds `X:0..3.2`, `Z:0..1.8288` (6ft), use:
```bash
./run_hardware.sh \
  --tag1 1 \
  --bridge-csv-3-mode xyz \
  --bridge-default-tag-id 1 \
  --bridge-x-scale 1.25 \
  --bridge-y-scale 1.6404199475 \
  --bridge-x-min 0 --bridge-x-max 4 \
  --bridge-y-min 0 --bridge-y-max 3 \
  --open
```
