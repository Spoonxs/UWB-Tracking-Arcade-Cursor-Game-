#!/usr/bin/env bash
set -euo pipefail

WEB_PORT=8000
OPEN_BROWSER=0
ENTRY="game_menu.html"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-port)
      WEB_PORT="${2:-8000}"
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
    -h|--help)
      cat <<'USAGE'
Usage: ./run_mouse.sh [--web-port <port>] [--entry <html>] [--open]
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ "$ENTRY" == "cursor_game.html" ]]; then
  URL="http://127.0.0.1:${WEB_PORT}/${ENTRY}?input=mouse"
else
  URL="http://127.0.0.1:${WEB_PORT}/${ENTRY}"
fi

echo "[run_mouse] starting web server on ${WEB_PORT}..."
echo "[run_mouse] open: ${URL}"
if [[ "$OPEN_BROWSER" == "1" ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
fi
python3 -m http.server "$WEB_PORT" --bind 127.0.0.1 --directory .
