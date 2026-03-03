# AGENTS.md

## Read First (Order)
1. `CLAUDE.md`
2. `GAME_MENU.md`
3. `RUNNER.md`
4. `SUIKA.md`
5. `WARIOWARE.md`
6. `BREAKOUT.md`
7. `CURSOR_GAME.md`
8. `RESEARCH_FINDINGS.md`
9. `RUN.md`
10. `progress.md`

## Current Product Direction
Build a **UWB ARCADE SUITE** in the browser where one UWB tag can control all games.

Primary launcher + games:
- `game_menu.html` (launcher)
- `runner.html`
- `suika.html`
- `warioware.html`
- `breakout.html`
- `cursor_game.html` (existing party mix)

Optional slot in menu:
- `fruit_ninja.html` (placeholder if not yet implemented)

## Required Build Order
Implement specs independently in this exact order:
1. `GAME_MENU.md`
2. `RUNNER.md`
3. `SUIKA.md`
4. `WARIOWARE.md`
5. `BREAKOUT.md`

## Shared Runtime Contract (All HTML Files)
Every game file must be fully self-contained and include:
- p5.js runtime
- One Euro filter smoothing
- WebSocket ingest (`ws://localhost:8765`)
- UWB mapping (meters -> screen)
- demo mouse fallback
- cursor/trail rendering
- ambient particles
- effects helpers (shake/flash/particles/floating text)
- `window.render_game_to_text()`
- `window.advanceTime(ms)`
- top-layer `← MENU` + `Esc` return to `game_menu.html`

No cross-file JS imports.

## UWB Hardware Integration (1 Tag + Multiple Anchors)
Target classroom/demo hardware path:
- Tag hardware: ESP32 UWB DW3000 (Tag 1)
- Anchors: 3+ anchors (target setup: 6 anchors)
- Computer link: Arduino Serial and/or UDP

Game input requirement:
- Games consume solved tag coordinates only: `x`, `y` in meters.
- UWB bounds are normalized to play area: `x=0..4`, `y=0..3`.
- Raw anchor distances are solved in `serial_to_udp.py` before reaching game files.

Accepted bridge payloads:
- `{"id":1,"x":1.23,"y":2.10}`
- `{"tags":[{"id":1,"x":1.23,"y":2.10}]}`

Transport pipeline:
1. ESP32/Arduino sends either solved `x,y` or anchor-distance JSON on Serial
2. `serial_to_udp.py` converts to solved tag `x,y` and forwards UDP
3. (Optional) firmware can send solved UDP directly to `127.0.0.1:9000`
4. `bridge.mjs` forwards UDP -> WebSocket (`ws://localhost:8765`)
5. All game files read from same WS stream

## Launch Modes
- Mouse-only tuning: `./run_mouse.sh`
- Simulation + bot helper: `./run_sim.sh --bot --open`
- Hardware-ready (tag mode): `./run_hardware.sh --tag1 1`

## Quality Bar
- Gameplay first: controls must stay responsive.
- Every mode needs explicit objective + failure condition.
- Difficulty ramps over time and is noticeable.
- Visual style should be cohesive and readable (not random icon soup).
- Menu navigation must work with dwell + click.
- All games must be playable with one tag in tag mode and with mouse in demo mode.

## Validation Checklist
- `node --check` passes on extracted JS for each HTML.
- Shell scripts parse clean (`bash -n`).
- Manual flow check for each game:
  - loads from menu
  - playable with cursor control
  - returns to menu with back button and `Esc`
  - win/lose or fail/retry flow works

## Known Environment Limits
- Playwright/browser automation may fail here if Chromium runtime libs are missing (observed: `libnspr4.so`).
- Socket binding can be restricted in this sandbox; rely on syntax/static checks when live ports are blocked.
