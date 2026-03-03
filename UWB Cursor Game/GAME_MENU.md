# GAME_MENU.md — Claude Code Build Specification

## Project Summary

A game launcher menu for the UWB cursor game system. The player uses a UWB tag as a physical cursor (or mouse in demo mode) to navigate a menu of full arcade games. Each game is a separate HTML file sharing the same cursor/WebSocket infrastructure.

This file describes the MENU PAGE and the SHARED INFRASTRUCTURE that every game reuses. Each individual game has its own spec file.

**Tech stack:** Each game is a single HTML file. p5.js from CDN. Vanilla JS. No build tools.

---

## CRITICAL INSTRUCTION

Build the menu page first. Then build each game one at a time using its own spec file. Every game file should copy the shared infrastructure from the menu (1€ filter, WebSocket, cursor rendering, demo mode) into itself so each game is fully self-contained and playable independently.

---

## Step 1: Menu Page Scaffold

### Goal
Create `game_menu.html` — a stylish launcher screen where the player selects which game to play using the UWB cursor.

### Requirements
- Load p5.js 1.9.0 from CDN, Google Font "Outfit" (300,400,600,800,900)
- Full-window canvas, dark background RGB(10,10,15)
- The menu IS the first thing the player sees. It should look polished and impressive.

### Configuration
Same CONFIG structure as other games:
- WebSocket URL ws://localhost:8765
- UWB bounds x 0-4m, y 0-3m
- Player 1 tag ID: 1, Player 2 tag ID: 2
- Cursor size 24px, trail length 12, P1 cyan, P2 magenta
- Demo timeout 3000ms

---

## Step 2: Shared Infrastructure

Every game (including this menu) uses these identical systems. Build them here first, then copy into each game file.

### 2a. One Euro Filter
Adaptive low-pass filter that smooths jitter when still and stays responsive when moving. Class with constructor(frequency, minCutoff=1.0, beta=0.007, dCutoff=1.0), a filter(value, timestamp) method, and reset(). Create a filter manager with separate instances per tag per axis. Convenience function: pass tag ID + raw X,Y → get smoothed X,Y.

Algorithm reference: github.com/casiez/OneEuroFilter

### 2b. WebSocket Connection
Connect to CONFIG.WS_URL. Bridge sends JSON with tag positions in meters. On message: map UWB coords to screen (X maps linearly with 100px padding, Y maps inverted), apply 1€ filter, store in player data. Auto-reconnect every 1 second on disconnect. Connection indicator: 8px dot top-left, green/red.

### 2c. Player/Cursor Data
Per detected tag: screenX, screenY, trail array (last 12 positions), active flag, color (cyan P1, magenta P2), label string. Update trail each frame: prepend current position, pop oldest if over limit.

### 2d. Demo Mode
If no WebSocket data for 3 seconds: P1 follows mouse with ±3px noise before filtering. P2 not simulated. Show "DEMO" badge top-right.

### 2e. Cursor Rendering
Draw back-to-front:
1. Trail: loop oldest→newest, each point as a circle decreasing in size (cursor size → 4px) and alpha (180 → 0) in player color at 35% alpha
2. Outer glow: radial gradient (concentric circles with decreasing alpha) at 2.5× cursor size, max alpha 30
3. Main dot: solid circle at cursor size, player color at 220 alpha
4. Bright center: white circle at 35% cursor size, 180 alpha
5. Label: "P1"/"P2" above cursor in 2-player mode

Hover detection helper: returns true if cursor center is within (target radius + cursor radius/2) of a target point.

### 2f. Ambient Particles
~50 tiny white dots (alpha 15-50, size 1-3px) drifting slowly upward. Respawn at bottom. Run across all states in every game.

### 2g. Screen Effects
- **Screen shake:** Intensity + duration → random translate offset that decays to zero
- **Screen flash:** Color + duration → full-screen overlay fading from alpha 120 to 0
- **Particle bursts:** Emit N particles at a point with color/speed. Each has random angle, velocity, size 3-8px, alpha 255, decay rate. Update: move by velocity, apply gravity (vy += 0.06), drag (vx *= 0.99), decrease alpha, shrink. Remove at zero alpha.
- **Floating scores:** "+XX" text drifting upward, fading over ~50 frames

---

## Step 3: Game Selection Menu

### Goal
A visual menu with game cards the player can select by hovering their cursor.

### Menu Layout
Title: "UWB ARCADE" in 72px bold white at top center.
Subtitle: "Move to select a game" in 18px, 50% opacity.

Below the title, display game cards in a 2×3 or 3×2 grid (adjust based on screen size). Each card represents one game:

### Game Cards (6 total)
1. **SUIKA** — Icon: circle with smaller circles inside. Color: orange. Tag: "Drop & Merge"
2. **RUNNER** — Icon: three vertical lines (lanes). Color: cyan. Tag: "Dodge & Dash"
3. **WARIOWARE** — Icon: lightning bolt. Color: yellow. Tag: "Micro Madness"
4. **FRUIT NINJA** — Icon: diagonal slash line. Color: lime green. Tag: "Slice & Dice"
5. **BREAKOUT** — Icon: horizontal bar with dots above. Color: magenta. Tag: "Brick Breaker"
6. **MINIGAMES** — Icon: four small squares. Color: white. Tag: "Party Mix" (this links to the existing cursor_game.html)

### Card Design
Each card is approximately 220×160px with:
- Dark background (slightly lighter than page background, ~RGB(18,18,28))
- Rounded corners (12px radius)
- The game's icon drawn procedurally (simple shapes, no images) centered in the card
- Game name in 20px bold below the icon
- Tag line in 12px at 50% opacity below the name
- A subtle border in the game's theme color at low alpha (~30)

### Hover Behavior
When the cursor overlaps a card:
- Card background brightens slightly
- Border glows brighter in the theme color (alpha increases to ~150)
- Card scales up slightly (102-105% — achieve by drawing slightly larger, not CSS transform)
- A soft glow appears behind the card in the theme color
- The cursor itself pulses brighter (hover feedback)

### Selection
When the cursor hovers over a card for 1.5 seconds continuously, the card "fills up" with a radial progress indicator (a ring that completes around the card border). When the ring completes:
- Brief flash in the game's theme color
- Navigate to the game's HTML file: use `window.location.href = 'suika.html'` (etc.)

Alternative: clicking/tapping selects immediately for mouse/touch users.

### Connection Status
Bottom of screen: show tag connection info and "DEMO" if applicable. Same format as other games.

### Back Navigation
Every individual game should have a small "← MENU" button in the top-left corner (or press ESC) that returns to game_menu.html.

### Verification
- [ ] Menu loads with title and 6 game cards in a grid
- [ ] Cards are visually distinct with unique colors and icons
- [ ] Hovering a card shows clear visual feedback (glow, scale, brightness)
- [ ] Holding cursor on a card for 1.5s triggers selection with progress ring
- [ ] Selection navigates to the correct game HTML file
- [ ] Cursor rendering and demo mode work on menu
- [ ] Ambient particles running in background

---

## Step 4: Shared "Back to Menu" System

### Goal
Every game needs a consistent way to return to the menu.

### Requirements
- Small "← MENU" text in the top-left corner of every game, 14px, 40% opacity
- Hovering it brightens to 100% opacity and shows underline
- Clicking/tapping or hovering for 1 second navigates back to game_menu.html
- Pressing ESC key also returns to menu from any game state
- This should be the LAST thing drawn each frame (on top of everything)

### Verification
- [ ] Back button visible in every game
- [ ] Hover feedback works
- [ ] ESC key returns to menu
- [ ] Navigation works correctly

---

## File Structure
```
game/
├── game_menu.html      (this spec — launcher menu)
├── suika.html          (SUIKA.md)
├── runner.html         (RUNNER.md)
├── warioware.html      (WARIOWARE.md)
├── fruit_ninja.html    (FRUIT_NINJA.md)
├── breakout.html       (BREAKOUT.md)
└── cursor_game.html    (CURSOR_GAME.md — already built)
```

Each HTML file is fully self-contained (includes its own copy of the shared infrastructure). No shared JS files, no imports between games. This keeps deployment dead simple — just serve the folder.
