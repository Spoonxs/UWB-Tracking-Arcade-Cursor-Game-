#!/usr/bin/env bash
set -euo pipefail

WEB_PORT=8000
UDP_PORT=9000
WS_PORT=8765
TAG1=1
TAG2=2
OPEN_BROWSER=0
ENTRY="game_menu.html"
SERIAL_PORTS=()
SERIAL_BAUD=115200
SERIAL_DEFAULT_TAG_IDS=""
SERIAL_ANCHORS_FILE="anchor_layout_6.json"
SERIAL_ANCHORS_SPEC=""
SERIAL_MIN_ANCHORS=3
SERIAL_DISTANCE_MAX=15
BRIDGE_DEFAULT_TAG_ID=1
BRIDGE_CSV_3_MODE="xyz"
BRIDGE_X_SCALE=1
BRIDGE_Y_SCALE=1
BRIDGE_X_OFFSET=0
BRIDGE_Y_OFFSET=0
BRIDGE_X_MIN=""
BRIDGE_X_MAX=""
BRIDGE_Y_MIN=""
BRIDGE_Y_MAX=""
BRIDGE_EMA_ALPHA="0.35"
BRIDGE_IMPL="python"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-port)
      WEB_PORT="${2:-8000}"
      shift 2
      ;;
    --udp-port)
      UDP_PORT="${2:-9000}"
      shift 2
      ;;
    --ws-port)
      WS_PORT="${2:-8765}"
      shift 2
      ;;
    --tag1)
      TAG1="${2:-1}"
      shift 2
      ;;
    --tag2)
      TAG2="${2:-2}"
      shift 2
      ;;
    --open)
      OPEN_BROWSER=1
      shift
      ;;
    --entry)
      ENTRY="${2:-game_menu.html}"
      shift 2
      ;;
    --serial-port)
      SERIAL_PORTS+=("${2:-}")
      shift 2
      ;;
    --serial-baud)
      SERIAL_BAUD="${2:-115200}"
      shift 2
      ;;
    --serial-default-tag-ids)
      SERIAL_DEFAULT_TAG_IDS="${2:-}"
      shift 2
      ;;
    --anchors-file)
      SERIAL_ANCHORS_FILE="${2:-anchor_layout_6.json}"
      shift 2
      ;;
    --anchors)
      SERIAL_ANCHORS_SPEC="${2:-}"
      shift 2
      ;;
    --min-anchors)
      SERIAL_MIN_ANCHORS="${2:-3}"
      shift 2
      ;;
    --distance-max)
      SERIAL_DISTANCE_MAX="${2:-15}"
      shift 2
      ;;
    --bridge-default-tag-id)
      BRIDGE_DEFAULT_TAG_ID="${2:-1}"
      shift 2
      ;;
    --bridge-csv-3-mode)
      BRIDGE_CSV_3_MODE="${2:-auto}"
      shift 2
      ;;
    --bridge-x-scale)
      BRIDGE_X_SCALE="${2:-1}"
      shift 2
      ;;
    --bridge-y-scale)
      BRIDGE_Y_SCALE="${2:-1}"
      shift 2
      ;;
    --bridge-x-offset)
      BRIDGE_X_OFFSET="${2:-0}"
      shift 2
      ;;
    --bridge-y-offset)
      BRIDGE_Y_OFFSET="${2:-0}"
      shift 2
      ;;
    --bridge-x-min)
      BRIDGE_X_MIN="${2:-}"
      shift 2
      ;;
    --bridge-x-max)
      BRIDGE_X_MAX="${2:-}"
      shift 2
      ;;
    --bridge-y-min)
      BRIDGE_Y_MIN="${2:-}"
      shift 2
      ;;
    --bridge-y-max)
      BRIDGE_Y_MAX="${2:-}"
      shift 2
      ;;
    --bridge-ema-alpha)
      BRIDGE_EMA_ALPHA="${2:-0.35}"
      shift 2
      ;;
    --bridge-impl)
      BRIDGE_IMPL="${2:-python}"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: ./run_hardware.sh [options]

Options:
  --web-port <port>   HTTP port (default 8000)
  --udp-port <port>   UDP input port for bridge (default 9000)
  --ws-port <port>    WS output port for game (default 8765)
  --tag1 <id>         Expected P1 tag id (default 1)
  --tag2 <id>         Expected P2 tag id (default 2)
  --entry <html>      Entry page (default game_menu.html)
  --serial-port <p>   Arduino serial port (repeat to launch serial_to_udp.py)
  --serial-baud <b>   Serial baud (default 115200)
  --serial-default-tag-ids <ids>
                      Comma list for serial_to_udp.py (default uses --tag1)
  --anchors-file <f>  Anchor layout JSON for serial_to_udp.py (default anchor_layout_6.json)
  --anchors <spec>    Extra anchor overrides (e.g. 'A1:0,0;A2:2,0;A3:4,0')
  --min-anchors <n>   Minimum anchors to solve position (default 3)
  --distance-max <m>  Max accepted anchor distance meters (default 15)
  --bridge-default-tag-id <id>
                      Default tag id used by bridge for xyz payloads (default 1)
  --bridge-csv-3-mode <mode>
                      How bridge parses 3-value CSV packets: auto|idxy|xyz (default xyz)
  --bridge-x-scale <v>  Bridge transform x=(x*scale)+offset (default 1)
  --bridge-y-scale <v>  Bridge transform y=(y*scale)+offset (default 1)
  --bridge-x-offset <v> Bridge x offset (default 0)
  --bridge-y-offset <v> Bridge y offset (default 0)
  --bridge-x-min <v>    Optional bridge x clamp min
  --bridge-x-max <v>    Optional bridge x clamp max
  --bridge-y-min <v>    Optional bridge y clamp min
  --bridge-y-max <v>    Optional bridge y clamp max
  --bridge-ema-alpha <v> EMA smoothing alpha 0..1 (default 0.35)
  --bridge-impl <name>  Bridge runtime: python|node (default python)
  --open              Try to open browser automatically
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$BRIDGE_IMPL" != "python" && "$BRIDGE_IMPL" != "node" ]]; then
  echo "Invalid --bridge-impl '$BRIDGE_IMPL' (expected python or node)" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p output
BRIDGE_LOG="output/run_hardware_bridge.log"
WEB_LOG="output/run_hardware_web.log"
SERIAL_LOG="output/run_hardware_serial.log"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[run_hardware] starting bridge..."
if [[ "$BRIDGE_IMPL" == "python" ]]; then
  bridge_cmd=(
    python3 bridge.py
    --udp-port "$UDP_PORT"
    --ws-port "$WS_PORT"
    --default-tag-id "$BRIDGE_DEFAULT_TAG_ID"
    --csv-3-mode "$BRIDGE_CSV_3_MODE"
    --x-scale "$BRIDGE_X_SCALE"
    --y-scale "$BRIDGE_Y_SCALE"
    --x-offset "$BRIDGE_X_OFFSET"
    --y-offset "$BRIDGE_Y_OFFSET"
    --ema-alpha "$BRIDGE_EMA_ALPHA"
  )
else
  bridge_cmd=(
    node bridge.mjs
    --udp-port "$UDP_PORT"
    --ws-port "$WS_PORT"
    --default-tag-id "$BRIDGE_DEFAULT_TAG_ID"
    --csv-3-mode "$BRIDGE_CSV_3_MODE"
    --x-scale "$BRIDGE_X_SCALE"
    --y-scale "$BRIDGE_Y_SCALE"
    --x-offset "$BRIDGE_X_OFFSET"
    --y-offset "$BRIDGE_Y_OFFSET"
  )
fi
if [[ -n "$BRIDGE_X_MIN" ]]; then
  bridge_cmd+=(--x-min "$BRIDGE_X_MIN")
fi
if [[ -n "$BRIDGE_X_MAX" ]]; then
  bridge_cmd+=(--x-max "$BRIDGE_X_MAX")
fi
if [[ -n "$BRIDGE_Y_MIN" ]]; then
  bridge_cmd+=(--y-min "$BRIDGE_Y_MIN")
fi
if [[ -n "$BRIDGE_Y_MAX" ]]; then
  bridge_cmd+=(--y-max "$BRIDGE_Y_MAX")
fi
"${bridge_cmd[@]}" >"$BRIDGE_LOG" 2>&1 &
PIDS+=("$!")

sleep 0.4

echo "[run_hardware] starting web server..."
python3 -m http.server "$WEB_PORT" --bind 127.0.0.1 --directory . >"$WEB_LOG" 2>&1 &
PIDS+=("$!")

if [[ "${#SERIAL_PORTS[@]}" -gt 0 ]]; then
  if [[ -z "$SERIAL_DEFAULT_TAG_IDS" ]]; then
    SERIAL_DEFAULT_TAG_IDS="${TAG1}"
  fi

  echo "[run_hardware] starting serial forwarder..."
  serial_cmd=(python3 serial_to_udp.py)
  for serial_port in "${SERIAL_PORTS[@]}"; do
    serial_cmd+=(--port "$serial_port")
  done
  serial_cmd+=(
    --baud "$SERIAL_BAUD"
    --default-tag-ids "$SERIAL_DEFAULT_TAG_IDS"
    --anchors-file "$SERIAL_ANCHORS_FILE"
    --min-anchors "$SERIAL_MIN_ANCHORS"
    --distance-max "$SERIAL_DISTANCE_MAX"
    --udp-host 127.0.0.1
    --udp-port "$UDP_PORT"
  )
  if [[ -n "$SERIAL_ANCHORS_SPEC" ]]; then
    serial_cmd+=(--anchors "$SERIAL_ANCHORS_SPEC")
  fi
  "${serial_cmd[@]}" >"$SERIAL_LOG" 2>&1 &
  PIDS+=("$!")
fi

COMMON_QUERY="tag1=${TAG1}&tag2=${TAG2}&ws=ws://127.0.0.1:${WS_PORT}"
if [[ "$ENTRY" == "cursor_game.html" ]]; then
  URL="http://127.0.0.1:${WEB_PORT}/${ENTRY}?input=tag&${COMMON_QUERY}"
else
  URL="http://127.0.0.1:${WEB_PORT}/${ENTRY}?${COMMON_QUERY}"
fi

echo
echo "[run_hardware] ready"
echo "  Game URL:    $URL"
echo "  Bridge log:  $BRIDGE_LOG"
echo "  Web log:     $WEB_LOG"
echo "  Bridge impl: $BRIDGE_IMPL"
if [[ "${#SERIAL_PORTS[@]}" -gt 0 ]]; then
  echo "  Serial log:  $SERIAL_LOG"
fi
echo ""
echo "Now send tag coordinates (x,y meters) to udp://127.0.0.1:${UDP_PORT}"
echo "Bridge CSV mode: ${BRIDGE_CSV_3_MODE} (default-tag-id=${BRIDGE_DEFAULT_TAG_ID})"
echo "Bridge smoothing ema-alpha: ${BRIDGE_EMA_ALPHA}"
echo "Bridge transform: x=(x*${BRIDGE_X_SCALE})+${BRIDGE_X_OFFSET}, y=(y*${BRIDGE_Y_SCALE})+${BRIDGE_Y_OFFSET}"
echo "or run serial forwarder from Arduino serial, for example:"
echo "  python3 serial_to_udp.py --port /dev/ttyUSB0 --baud 115200 --default-tag-ids ${TAG1} --anchors-file anchor_layout_6.json"
if [[ "${#SERIAL_PORTS[@]}" -gt 0 ]]; then
  echo ""
  echo "Serial forwarder is active on: ${SERIAL_PORTS[*]}"
fi
echo ""
echo "Stop: Ctrl+C"

echo
if [[ "$OPEN_BROWSER" == "1" ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
fi

wait
