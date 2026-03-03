# Run UWB Arcade Suite

## Entry points
Default launcher page:
- `http://127.0.0.1:8000/game_menu.html`

Direct game pages:
- `game_menu.html`
- `runner.html`
- `suika.html`
- `warioware.html`
- `breakout.html`
- `cursor_game.html`
- `fruit_ninja.html` (placeholder)

## Quick start (mouse-only)
```bash
./run_mouse.sh
```

## Windows PowerShell quickstart (ESP32 UDP on port 9000)
```powershell
cd "C:\Users\obara\Documents\UWB Cursor Game"
.\quickstart_windows.ps1
```

To stop quickstart processes later:
```powershell
$p = Get-Content .\output\quickstart_pids.json | ConvertFrom-Json
Stop-Process -Id $p.bridge_pid,$p.web_pid
```

This starts (Python-only):
- `bridge.py` (`udp 9000 -> ws 8765`)
- web server (`http://127.0.0.1:8000`)

And uses axis mapping:
- `x <- packet.x` (left/right)
- `y <- packet.z` (vertical on screen)
- `packet.y` is depth/out-of-screen

Quickstart defaults:
- `TrackerXMin=0`, `TrackerXMax=3.2`
- `TrackerZMin=0`, `TrackerZMax=1.8288` (6ft)
- bridge smoothing `BridgeEmaAlpha=0.35`

Manual dependency install (if needed):
```bash
python3 -m pip install websockets
```

Open a specific page:
```bash
./run_mouse.sh --entry runner.html
./run_mouse.sh --entry suika.html
./run_mouse.sh --entry cursor_game.html
```

## Quick start (simulation)
```bash
./run_sim.sh
```

Useful options:
```bash
./run_sim.sh --tags 2 --movement random --open
./run_sim.sh --entry breakout.html --open
./run_sim.sh --bot --open   # opens cursor_game bot mode
```

## Hardware-ready mode (bridge + web, no simulator)
```bash
./run_hardware.sh --tag1 1
```

Hardware mode with Arduino serial + 6-anchor solve in one command:
```bash
./run_hardware.sh --tag1 1 --serial-port /dev/ttyUSB0 --anchors-file anchor_layout_6.json --open
```

If your tag firmware sends UDP as `x,y,z` (like `CoordsVisualizer2.0.py` expects),
run bridge in `xyz` CSV mode:
```bash
./run_hardware.sh --tag1 1 --bridge-csv-3-mode xyz --bridge-default-tag-id 1 --open
```

If your tracked space is `X:0..3.2`, `Z:0..1.8288` (6ft) and you want game-space `X:0..4`, `Y:0..3`:
(`Y` is treated as depth/out-of-screen in this mode)
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

Open a specific page:
```bash
./run_hardware.sh --entry game_menu.html --tag1 1
./run_hardware.sh --entry cursor_game.html --tag1 1 --tag2 2
```

## 1) Start bridge manually (optional)
Recommended (Python):
```bash
python3 bridge.py --udp-port 9000 --ws-port 8765 --csv-3-mode xyz --default-tag-id 1
```

Alternative (Node):
```bash
node bridge.mjs --udp-port 9000 --ws-port 8765
```

All games listen on WebSocket:
- `ws://localhost:8765`

## 2) Serve files manually (optional)
```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory .
```

Then open:
- `http://127.0.0.1:8000/game_menu.html`

## 3) Feed data to bridge

### Real ESP32 tags (UDP path)
Send solved coordinates to `127.0.0.1:9000`:
- `{"id":1,"x":1.2,"y":2.1}`
- `{"tags":[{"id":1,"x":1.2,"y":2.1},{"id":2,"x":2.5,"y":1.4}]}`

Also supported now:
- raw `x,y,z` CSV where game axes are `x<-x`, `y<-z` (`y` in packet is depth), with `--bridge-csv-3-mode xyz`

### Simulator
```bash
python3 simulate_tags.py --tags 1
python3 simulate_tags.py --tags 2
```

Research repo simulator model:
```bash
python3 simulate_research_repo_tags.py --tags 1 --movement circle
python3 simulate_research_repo_tags.py --tags 2 --movement random
```

## 4) Arduino Serial -> UDP forwarding path (ESP32 UWB DW3000)

Games consume tag coordinates (`x`,`y`) over WebSocket.
`serial_to_udp.py` now supports both:
- already-solved coordinates (`x`,`y`)
- raw anchor distances (`A1..A6`) and solves `x`,`y` using multilateration

### Steps
1. Install serial dependency:
```bash
python3 -m pip install --user pyserial
```

2. Find ports:
```bash
python3 list_serial_ports.py
```

3. Run bridge:
```bash
python3 bridge.py --udp-port 9000 --ws-port 8765 --csv-3-mode xyz --default-tag-id 1
```

4. Forward Serial to UDP:
```bash
# 1 tag + 6 anchors (recommended)
python3 serial_to_udp.py \
  --port /dev/ttyUSB0 \
  --baud 115200 \
  --default-tag-ids 1 \
  --anchors-file anchor_layout_6.json \
  --min-anchors 3

# 2 tags
python3 serial_to_udp.py --port /dev/ttyUSB0 --port /dev/ttyUSB1 --baud 115200 --default-tag-ids 1,2
```

Alternative: let launcher start serial forwarder for you:
```bash
./run_hardware.sh \
  --tag1 1 \
  --serial-port /dev/ttyUSB0 \
  --anchors-file anchor_layout_6.json \
  --min-anchors 3 \
  --open
```

5. Open launcher:
- `http://127.0.0.1:8000/game_menu.html`

Accepted serial line formats:
- `{"id":1,"x":1.23,"y":2.10}`
- `{"tags":[...]}`
- `{"tag":"T1","anchors":[{"id":"A1","distance":1.23},{"id":"A2","distance":2.34},{"id":"A3","distance":2.02}]}`
- `1,1.23,2.10`
- `id=1 x=1.23 y=2.10`
- `tag=T1 A1=1.23 A2=2.34 A3=2.02`

### Anchor layout notes (1 tag, 6 anchors)
- Edit `anchor_layout_6.json` to match your real anchor coordinates in meters.
- Keep coordinates in the same reference frame as your play area.
- If your room is larger/smaller than game bounds, tune using:
  - `--x-scale`, `--y-scale`
  - `--x-offset`, `--y-offset`
  - `--x-min`, `--x-max`, `--y-min`, `--y-max`

## Keyboard controls (common)
- `Space`: start/restart/launch (game-specific)
- `D`: toggle forced demo mode
- `Esc`: return to menu

`cursor_game.html` also supports:
- `I`: cycle input mode
- `B`: toggle bot assist
- `Z`: calibration action (start/capture next corner)
- On-screen `CALIBRATE` button (top-center control dock), corner order: `BL -> BR -> TL -> TR`
- `R`: reset to menu
- `2`: toggle 2-player mode on menu

Calibration is shared across pages:
- Run calibration once in `cursor_game.html`.
- Profile is saved in browser storage and used by `game_menu.html`, `runner.html`, `suika.html`, `warioware.html`, `breakout.html`, and `fruit_ninja.html`.
- Sequence is 5 actions total: `CALIBRATE` (start) then capture `BL`, `BR`, `TL`, `TR`.
