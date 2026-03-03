# RUNNER.md — Claude Code Build Specification

## Project Summary

A Subway Surfers-style endless runner controlled by UWB cursor. The player's cursor X position maps to three lanes (left/center/right). Cursor Y position controls jumping (high) and sliding (low). Obstacles approach from the top of the screen, the player dodges by switching lanes and jumping/sliding. Coins to collect, speed increases over time, power-ups for bonus effects.

**File:** `runner.html` — single self-contained HTML file with p5.js.

**Shared infrastructure:** Copy 1€ filter, WebSocket, cursor rendering, demo mode, ambient particles, effects from GAME_MENU.md. Include "← MENU" back button and ESC handler.

---

## CRITICAL INSTRUCTION

Build step-by-step. Get the scrolling road and lane system working first. Then obstacles. Then scoring. Then power-ups last.

---

## Step 1: Scrolling Road and Lane System

### Goal
Create the endless scrolling road with three distinct lanes.

### Road Layout
The road occupies the center ~60% of the screen width. Three equal-width lanes. The road scrolls from top to bottom to simulate forward movement.

### Scrolling Effect
Draw horizontal dashed lane dividers that scroll downward continuously. The scroll speed starts at 4 pixels/frame and increases over time. Road edge lines (solid, brighter) on the left and right boundaries.

### Perspective (Optional Enhancement)
For a more dynamic look, make the road slightly narrower at the top and wider at the bottom (trapezoidal). Lane dividers converge toward a vanishing point near the top center. This creates a simple perspective illusion without real 3D math.

### Background
The areas outside the road are dark with scrolling elements to sell the sense of speed: tiny dots or dashes streaming downward, faster than the road lines. These represent the environment rushing past.

### Player Character
A simple neon figure at the bottom third of the screen. Not a cursor — the cursor controls WHERE the character goes, but the character is drawn as a small humanoid or geometric shape in the active lane.

The character design: a bright glowing diamond/rhombus shape (about 30px wide, 45px tall) with a small trail behind it. Color: cyan for P1. The character smoothly slides between lanes (lerp over 8-10 frames, not instant teleport).

### Lane Mapping from Cursor
Divide the screen into three horizontal zones based on cursor X:
- Cursor in left third of screen → character in left lane
- Cursor in middle third → center lane
- Cursor in right third → right lane

The character lerps to the target lane position for smooth movement.

### Verification
- [ ] Road scrolls downward continuously with dashed lane dividers
- [ ] Three lanes clearly visible
- [ ] Moving cursor left/right switches character between lanes smoothly
- [ ] Speed scrolling creates sense of forward motion
- [ ] Character is a distinct neon shape, not just the cursor dot

---

## Step 2: Obstacles

### Goal
Obstacles spawn at the top and scroll down. The player must dodge by being in a different lane.

### Obstacle Types

**Barrier (ground level):** A solid rectangular block occupying one lane. Player must switch to a different lane to avoid. Draw as a bright red/orange glowing rectangle with rounded corners.

**Low barrier:** A shorter obstacle — player can jump over it OR switch lanes. Draw as a flatter rectangle with a different color (amber).

**Overhead barrier:** A floating obstacle — player must slide under it OR switch lanes. Draw as a rectangle floating above ground level with a distinct color (purple) and a shadow below it.

**Full-width barrier with gap:** Spans 2 of 3 lanes, forcing the player into the one open lane. Uses the same visual as regular barriers but wider.

### Obstacle Spawning
Spawn obstacles at intervals that decrease as speed increases. Start with one obstacle every 60-80 frames. At higher speeds, every 30-40 frames. Randomly choose obstacle type and lane. Never spawn an impossible pattern (ensure at least one lane is always passable at any given Y position — check that consecutive obstacles don't block all three lanes simultaneously).

### Collision
Each frame, check if the player character overlaps any obstacle. Simple rectangle-rectangle overlap test based on lane position and Y range.

On collision: lose a life (start with 3), brief invincibility for 2 seconds (character flashes), screen shake, red flash. If lives reach zero, game over.

### Verification
- [ ] Obstacles scroll from top to bottom at road speed
- [ ] Different obstacle types are visually distinct
- [ ] Switching lanes dodges obstacles correctly
- [ ] Collision detection works — hitting obstacle costs a life
- [ ] Invincibility frames prevent instant multi-death
- [ ] No impossible obstacle patterns generated

---

## Step 3: Jumping and Sliding

### Goal
Add vertical movement for dodging low and overhead obstacles.

### Jump/Slide Mapping from Cursor Y
- Cursor in top third of screen → character jumps
- Cursor in middle third → character runs (normal)
- Cursor in bottom third → character slides/ducks

### Jump Animation
When cursor is in the top zone: character rises upward by ~60px over 6 frames, holds for a moment, then falls back over 6 frames. While airborne, the character clears low barriers (collision check skips ground-level obstacles during jump peak). The character gets a slight scale increase and a shadow on the ground below showing height.

### Slide Animation
When cursor is in the bottom zone: character squashes vertically (becomes wider and shorter) and drops lower. This clears overhead barriers. The character leaves a brief trail streak on the ground. Slide lasts as long as cursor stays in the bottom zone.

### Visual Feedback
Show zone indicators on the side of the screen: faint "JUMP" text at the top, "SLIDE" text at the bottom. These flash briefly when the player enters each zone. The character should have distinct visual states for running, jumping (arms up, glow trail below), and sliding (wide, low, streak behind).

### Verification
- [ ] Cursor position maps to jump/run/slide states
- [ ] Jumping clears ground-level obstacles
- [ ] Sliding clears overhead obstacles
- [ ] Visual states are clearly different
- [ ] Zone indicators help player understand the controls

---

## Step 4: Coins and Scoring

### Goal
Add collectible coins in the lanes and a scoring system.

### Coins
Small glowing circles (12px radius) in the lane centers. Spawn in patterns: single coins, rows of 3-5 in a line, arcs, zigzag patterns across lanes. Color: gold/yellow with a soft glow.

Coins scroll down with the road. When the player character overlaps a coin: collect it (+10 points), coin disappears with a brief sparkle particle burst, floating "+10" score.

### Distance Score
In addition to coin score, award 1 point per frame survived. Display as a "distance" meter.

### Score Display
- Top-center: large score number (combo of coin points + distance)
- Top-right: coin counter with a small coin icon
- Current speed/distance as a secondary stat

### Combo System
Collecting coins in quick succession (within 30 frames of each other) builds a multiplier. ×2 after 3 coins, ×3 after 6, ×4 after 10. The multiplier resets if you go 30+ frames without collecting. Show the multiplier next to the score in a bright color when active.

### Speed Ramp
Increase scroll speed by 0.002 per frame (very gradual). This means the game gets progressively harder. Every 1000 distance points, briefly flash "SPEED UP!" text.

### Verification
- [ ] Coins appear in lanes and scroll with the road
- [ ] Collecting coins gives points with particles and floating score
- [ ] Combo multiplier builds and resets correctly
- [ ] Speed gradually increases, making the game harder
- [ ] Score display shows all relevant info

---

## Step 5: Power-Ups

### Goal
Add occasional power-up items that give temporary abilities.

### Power-Up Types

**Magnet (blue glow):** For 5 seconds, coins within 100px are attracted toward the player. All coins in adjacent lanes drift toward the player's lane.

**Shield (green glow):** Absorbs one hit without losing a life. Shown as a green aura around the character. Breaks on impact with particles.

**Score Doubler (gold glow):** All points are doubled for 5 seconds. Score text turns gold during this period.

**Shrink (purple glow):** Character becomes 50% smaller for 5 seconds, making it easier to dodge obstacles in tight gaps.

### Spawning
Power-ups appear roughly every 15-20 seconds. They look like glowing diamond shapes rotating slowly, clearly different from coins and obstacles. They float in a lane and scroll with the road.

### Active Power-Up Indicator
When a power-up is active, show a small icon + timer bar in the top-left area (below the back button). The bar depletes as the power-up duration runs out.

### Verification
- [ ] Power-ups spawn occasionally and are visually distinct from coins/obstacles
- [ ] Each power-up effect works correctly and lasts ~5 seconds
- [ ] Active indicator shows which power-up is running and remaining time
- [ ] Magnet visibly attracts nearby coins

---

## Step 6: Game Over, Start Screen, and Polish

### Goal
Complete game flow and polish.

### Start Screen
"RUNNER" title in 64px. Instructions: "Move LEFT/RIGHT to switch lanes. Move UP to jump, DOWN to slide." Show the three zone indicators. "Press SPACE or hold still to start." Brief countdown 3-2-1 before gameplay begins.

### Game Over Screen
Freeze the scene. "GAME OVER" text with final score count-up. Show stats: distance, coins collected, best combo. "Press SPACE to retry." Session high score display.

### Polish
- Road surface has a subtle dark grid texture scrolling with it
- Obstacle destruction: when passed successfully, obstacles fade out behind the player (or fall away)
- Speed lines: at higher speeds, add horizontal streaks on the sides
- Character trail: at higher speeds, the trail behind the character gets longer and brighter
- Near-miss bonus: passing an obstacle with <20px clearance awards +5 bonus with "CLOSE!" text

### Verification
- [ ] Start screen with instructions loads first
- [ ] Game over shows stats and retry
- [ ] Speed lines appear at higher speeds
- [ ] Near-miss detection and bonus work
- [ ] Complete run from start to game-over feels smooth
