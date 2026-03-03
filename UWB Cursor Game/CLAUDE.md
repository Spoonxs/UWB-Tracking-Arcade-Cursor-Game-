# CLAUDE.md

## Mission
Iterate `cursor_game.html` into a polished **osu + Dumb Ways to Die** style arcade game that works in:
- mouse mode
- simulation mode
- real 1-tag/2-tag UWB mode

## Project Constraints
- Single HTML file + p5.js CDN.
- Data input over WebSocket (`ws://localhost:8765`).
- Preserve UWB compatibility and One Euro smoothing for tag data.

## Active Priorities
1. Keep controls responsive (mouse must feel immediate).
2. Keep minigames high-stakes (clear fail states).
3. Improve bot consistency in hard rounds.
4. Improve visual style with real assets, not only procedural circles.
5. Keep round-to-round variety high (layout/path/pattern randomization).
6. Get user sign-off before major visual restyles.

## Gameplay Direction
- Short, intense microgames.
- Strong transitions (`SAFE!/SPLAT!` style feedback).
- Difficulty ramps aggressively by round.
- Add rhythm + hazard + precision challenge variety.
- Avoid repeating the same challenge geometry on each replay.

## Bot Direction
- Per-minigame strategy, not one generic strategy.
- Add lookahead for predictive hazards.
- Use deterministic movement in bot mode; avoid noise jitter.
- Validate with multi-cycle sim runs.

## Visual Asset Direction (Very Important)
The current procedural visuals are transitional. Move to real art assets:
- Hazard icons, stickers, warning signs, playful characters
- Distinct UI frames/badges/panels
- Themed minigame art motifs (rhythm, danger, absurdity)
- Keep motifs cohesive; avoid unrelated icon mixes that look procedural/random.

Create and maintain:
- `assets/sprites/`
- `assets/ui/`
- `assets/audio/`
- `assets/licenses/ASSET_CREDITS.md`

Only use assets with clear reuse rights.

### Current Visual Baseline
- Current runtime visuals are intentionally simplified.
- Active art uses:
  - `assets/generated/sprites_screen/*.png` (core gameplay sprites)
  - `assets/sprites/tabler/skull.svg` (life indicator)
- Unused assets are archived in `assets/_unused/`.

## Current Minigame Baseline
- Active set: `TAP TARGETS`, `DODGE`, `WHACK-A-MOLE`, `RED LIGHT GREEN LIGHT`, `COLLECT & AVOID`, `RHYTHM RUSH`, `TRACE THE PATH`.
- `LASER SWEEP` and `SAFE SPOTS` were removed for stability.
- Existing games now include pattern/layout variety across rounds:
  - red light route families
  - dodge mode families
  - whack board + spawn families
  - trace path style families

## Dev/Run
- Mouse-only: `./run_mouse.sh`
- Sim + bot: `./run_sim.sh --bot --open`
- Hardware-ready: `./run_hardware.sh --tag1 1`

## Debug Checklist
- Connection indicator reflects expected mode.
- Input mode/bot mode shown correctly in menu.
- Minigame objective text matches real win condition.
- No silent auto-pass on timeout unless intentional.
- Verify round variety manually (no repeated identical geometry/pacing loop).

## Automation Hooks
- `window.render_game_to_text()`
- `window.advanceTime(ms)`
