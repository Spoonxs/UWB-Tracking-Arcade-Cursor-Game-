#!/usr/bin/env bash
set -euo pipefail

# One-command launcher for local simulation:
# - UDP bridge (9000 -> ws://127.0.0.1:8765)
# - Research movement simulator
# - Static web server (http://127.0.0.1:8000)

TAGS=1
MOVEMENT="circle"
WEB_PORT=8000
UDP_PORT=9000
WS_PORT=8765
OPEN_BROWSER=0
BOT=0
ENTRY="game_menu.html"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tags)
      TAGS="${2:-1}"
      shift 2
      ;;
    --movement)
      MOVEMENT="${2:-circle}"
      shift 2
      ;;
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
    --open)
      OPEN_BROWSER=1
      shift
      ;;
    --bot)
      BOT=1
      shift
      ;;
    --entry)
      ENTRY="${2:-game_menu.html}"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: ./run_sim.sh [options]

Options:
  --tags <1|2>             Number of simulated tags (default: 1)
  --movement <circle|random>
                           Simulator movement style (default: circle)
  --web-port <port>        HTTP port for game page (default: 8000)
  --udp-port <port>        UDP port for bridge input (default: 9000)
  --ws-port <port>         WebSocket port for game input (default: 8765)
  --entry <html>           Entry page (default: game_menu.html)
  --open                   Try to open browser automatically
  --bot                    Open cursor_game in bot-assist mouse mode
  -h, --help               Show this help
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$TAGS" != "1" && "$TAGS" != "2" ]]; then
  echo "--tags must be 1 or 2" >&2
  exit 2
fi
if [[ "$MOVEMENT" != "circle" && "$MOVEMENT" != "random" ]]; then
  echo "--movement must be circle or random" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p output
BRIDGE_LOG="output/run_sim_bridge.log"
SIM_LOG="output/run_sim_simulator.log"
WEB_LOG="output/run_sim_web.log"

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

echo "[run_sim] starting bridge..."
node bridge.mjs --udp-port "$UDP_PORT" --ws-port "$WS_PORT" >"$BRIDGE_LOG" 2>&1 &
PIDS+=("$!")

sleep 0.4

echo "[run_sim] starting simulator (tags=$TAGS movement=$MOVEMENT)..."
python3 simulate_research_repo_tags.py --tags "$TAGS" --movement "$MOVEMENT" --port "$UDP_PORT" >"$SIM_LOG" 2>&1 &
PIDS+=("$!")

sleep 0.4

echo "[run_sim] starting web server..."
python3 -m http.server "$WEB_PORT" --bind 127.0.0.1 --directory . >"$WEB_LOG" 2>&1 &
PIDS+=("$!")

COMMON_QUERY="tag1=1&tag2=2&ws=ws://127.0.0.1:${WS_PORT}"
URL="http://127.0.0.1:${WEB_PORT}/${ENTRY}?${COMMON_QUERY}"
if [[ "$BOT" == "1" ]]; then
  URL="http://127.0.0.1:${WEB_PORT}/cursor_game.html?input=mouse&bot=1&${COMMON_QUERY}"
fi

echo
echo "[run_sim] ready"
echo "  Game URL: $URL"
echo "  Bridge log: $BRIDGE_LOG"
echo "  Sim log:    $SIM_LOG"
echo "  Web log:    $WEB_LOG"
echo "  Stop: Ctrl+C"
echo

if [[ "$OPEN_BROWSER" == "1" ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
fi

# Keep script alive while children run.
wait
