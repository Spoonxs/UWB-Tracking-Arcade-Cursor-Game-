# WARIOWARE.md — Claude Code Build Specification

## Project Summary

A WarioWare-style rapid-fire microgame collection. Each microgame lasts only 3-5 seconds. A one-word instruction flashes on screen ("DODGE!", "POP!", "TRACE!"), the player must figure out what to do and do it before time runs out. Speed increases every 4 games. Lives are lost on failure. The chaos and speed are the fun.

**File:** `warioware.html` — single self-contained HTML file with p5.js.

**Shared infrastructure:** Copy 1€ filter, WebSocket, cursor rendering, demo mode, effects from GAME_MENU.md. Include "← MENU" back button and ESC.

---

## CRITICAL INSTRUCTION

Build the framework and speed system first. Then add microgames ONE AT A TIME. Start with 4-5 simple ones, verify the speed/flow feels right, then add more. Target 12+ microgames for variety.

---

## Step 1: Microgame Framework and Speed System

### Goal
Build the engine that runs microgames in sequence with increasing speed.

### Game Flow
```
Title Screen → Ready prompt → Microgame → Result flash → (repeat) → Game Over
```

### Speed Levels
The game has a "speed level" starting at 1. Every 4 microgames completed, speed level increases by 1. Max speed level: 8.

Speed affects:
- Microgame duration: starts at 4 seconds at level 1, decreases to ~2 seconds at level 8. Formula: `4000 - (speedLevel - 1) * 280` milliseconds, minimum 1700ms.
- Transition speed: the "WIN"/"LOSE" flash and the next instruction appear faster.
- Some microgames use the speed level to increase their internal difficulty (more targets, faster objects, etc.)

### Lives
Start with 4 lives (displayed as hearts or dots). Losing a microgame costs one life. Zero lives = game over.

### Between Microgames
After each microgame resolves (win or lose):
1. Flash "WIN!" in green (300ms at speed 1, 150ms at speed 8) or "LOSE!" in red
2. If speed level increased, flash "SPEED UP!" in large yellow text for 500ms with screen shake
3. Show the one-word instruction for the NEXT microgame in huge bold text (e.g., "DODGE!") for 800ms at speed 1, 400ms at speed 8
4. Begin the next microgame

### Microgame Interface
Each microgame is an object with:
- **command:** The one-word instruction shown to the player (e.g., "POP!", "DODGE!", "TRACE!")
- **setup(speedLevel):** Initialize the microgame state
- **update(players, speedLevel):** Run each frame. Return null to continue, or {won: true/false} to end.
- **draw():** Render the microgame. Cursor is drawn by the framework after this.

### Microgame Selection
Shuffle all microgames into a random order. Play through the shuffled list. When all have been played, reshuffle and repeat. Never play the same microgame twice in a row.

### Verification
- [ ] Framework cycles through microgames with instruction → play → result flow
- [ ] Speed level increases every 4 games
- [ ] Duration gets shorter at higher speeds
- [ ] Lives decrement on failure
- [ ] Game over triggers at zero lives
- [ ] "SPEED UP!" appears on level transitions

---

## Step 2: HUD and Framing

### Goal
Persistent HUD elements and the "TV frame" aesthetic.

### WarioWare Border
Draw a decorative border around the gameplay area — a thick rounded rectangle frame (~20px) in a rotating rainbow hue (slowly cycles through colors via hue shift). This gives the WarioWare "TV screen" feel. The gameplay happens INSIDE this frame.

### HUD (outside or overlapping the frame)
- **Top-left:** Lives as dots/hearts
- **Top-right:** Score counter
- **Top-center:** Speed level indicator ("SPD: 3" or show as filled bars)
- **Bottom-center:** Timer bar that depletes during each microgame. Starts as the frame color, turns red when <25% remaining.

### Score
+100 points per microgame won. Bonus +50 for each speed level above 1 (so at speed 3, winning gives 200). On game over: show total score with stats.

### Verification
- [ ] Decorative border visible with cycling color
- [ ] Lives, score, speed level all displayed
- [ ] Timer bar depletes per microgame
- [ ] Score calculation correct with speed bonus

---

## Step 3: Microgames — First Batch (build these one at a time)

### Microgame: POP!
**Command:** "POP!"
**Description:** 5-8 bubbles float around the screen. Pop all of them by moving the cursor into them.
**Win condition:** All bubbles popped before time runs out.
**Scaling:** More bubbles at higher speed, bubbles move faster and are smaller.
**Visual:** Translucent circles with a bright rim. Pop animation: expand briefly and fade with 6-8 particles.

### Microgame: DODGE!
**Command:** "DODGE!"
**Description:** A large red bar sweeps across the screen (horizontal, moving top to bottom). Don't let it touch your cursor.
**Win condition:** Survive until time runs out without being hit.
**Scaling:** At higher speeds, more bars sweep simultaneously, or bars move faster.
**Visual:** Red glowing rectangle with motion blur trail. Screen flashes red if hit.

### Microgame: CATCH!
**Command:** "CATCH!"
**Description:** An object (glowing star shape) falls from a random position at the top. Move cursor to catch it before it hits the bottom.
**Win condition:** Cursor overlaps the falling object before it reaches the bottom.
**Scaling:** Object falls faster. At speed 3+, two objects fall at once (catch both).
**Visual:** Gold spinning star with trail. Catch triggers satisfying burst of gold particles.

### Microgame: FREEZE!
**Command:** "FREEZE!"
**Description:** The screen says FREEZE. The player must NOT move their cursor. Any movement more than 10px fails.
**Win condition:** Cursor stays still for the entire duration.
**Scaling:** Duration stays the same but the screen shows distracting animations (shaking elements, flashing colors) trying to trick the player into moving.
**Visual:** Blue-tinted screen with snowflake particles. A "movement meter" bar that fills red if you move.

### Microgame: BIGGER!
**Command:** "BIGGER!"
**Description:** Two circles appear side by side, close in size but one is slightly larger. Move cursor to the bigger one.
**Win condition:** Cursor is inside the bigger circle when time runs out (or touches it).
**Scaling:** Size difference shrinks at higher speeds (harder to tell). At speed 5+, three circles appear.
**Visual:** Two clean white circles on dark background. Correct choice flashes green, wrong flashes red.

### Verification (per microgame)
- [ ] Instruction text matches the game
- [ ] Win/lose conditions work correctly
- [ ] Difficulty scales with speed level
- [ ] Visual feedback is clear and immediate
- [ ] Each game is understandable within ~1 second of seeing the instruction

---

## Step 4: Microgames — Second Batch

### Microgame: TRACE!
**Command:** "TRACE!"
**Description:** A simple shape outline appears (circle, triangle, or square). The player must trace along the outline with their cursor.
**Win condition:** Cursor visits >70% of checkpoints along the shape path.
**Scaling:** More complex shapes at higher speeds (pentagon, star). Stricter accuracy.
**Visual:** Glowing outline with small checkpoint dots that light up green as the cursor passes them.

### Microgame: SHAKE!
**Command:** "SHAKE!"
**Description:** A container/bottle appears on screen. Move cursor back and forth rapidly (left-right) to "shake" it. A fill meter shows progress.
**Win condition:** Fill meter reaches 100%.
**Scaling:** Need more shaking at higher speeds to fill the meter.
**Visual:** A simple bottle shape that shakes with the cursor. Bubbles appear inside as you shake. Meter fills with fizzy animation.

### Microgame: AVOID!
**Command:** "AVOID!"
**Description:** Expanding circles (like ripples/shockwaves) grow outward from random points. Move cursor to gaps between them.
**Win condition:** Don't get hit by any expanding circle.
**Scaling:** More circles, faster expansion, overlapping patterns.
**Visual:** Neon rings expanding outward. Hit = bright flash and ring color shifts to red.

### Microgame: GATHER!
**Command:** "GATHER!"
**Description:** 8-12 small dots are scattered across the screen. Move cursor near them to attract them. Bring all dots to the center zone.
**Win condition:** All dots are within the center zone.
**Scaling:** More dots, weaker attraction (cursor must get closer). Dots drift away from center.
**Visual:** Tiny glowing particles that follow cursor at a distance. Center zone is a pulsing circle. Dots turn green when inside the zone.

### Microgame: MATCH!
**Command:** "MATCH!"
**Description:** A colored circle appears at the top. Three circles of different colors appear at the bottom. Move cursor to the one that matches.
**Win condition:** Cursor touches the matching color.
**Scaling:** Colors become more similar (e.g., two slightly different reds). At speed 5+, match by SIZE instead of color. At speed 7+, match by both.
**Visual:** Clean circles with bold colors. Wrong choice flashes the circle red. Right choice explodes green.

### Verification (per microgame)
- [ ] Each game is winnable even at speed 1 (approachable)
- [ ] Each game is stressful but possible at speed 5+
- [ ] Instruction word clearly communicates what to do
- [ ] Games feel distinct from each other

---

## Step 5: Microgames — Third Batch

### Microgame: FLEE!
**Command:** "FLEE!"
**Description:** A red "enemy" circle chases the cursor. It accelerates toward the cursor position. Don't let it touch you.
**Win condition:** Survive without being caught.
**Scaling:** Enemy moves faster. At speed 4+, two enemies. At speed 7+, three.
**Visual:** Red pulsing circle with angry face (two dots + frown). Leaves red particle trail. Impact = explosion.

### Microgame: STACK!
**Command:** "STACK!"
**Description:** Blocks fall from the top, one at a time. Move cursor to position each block. Stack 3-4 blocks into a stable tower without toppling.
**Win condition:** All blocks placed and tower stands for 1 second.
**Scaling:** More blocks to stack. Blocks fall faster. Narrower blocks.
**Visual:** Bright colored rectangles. Stacked blocks wobble slightly. Tower collapse has physics-like animation (blocks tumble with rotation).

### Microgame: SLICE!
**Command:** "SLICE!"
**Description:** A glowing line (like a rope) stretches across the screen. Move cursor across it to "cut" it. Multiple ropes appear.
**Win condition:** Cut all ropes.
**Scaling:** More ropes. They appear at angles. Some are moving. At speed 6+, avoid red ropes (cutting them = lose).
**Visual:** Neon lines that snap apart with spark particles when cursor crosses them. Cut ends retract.

### Microgame: COUNT!
**Command:** "COUNT!"
**Description:** A number flashes on screen briefly (e.g., "3"). Then N objects appear scattered on screen. Move cursor to the area with exactly that many objects.
**Win condition:** Cursor is in the correct group.
**Scaling:** Objects are more spread out. Groups overlap visually. Number shown for less time. 
**Visual:** Bright dots in groups with soft circle zones. Correct zone glows green, wrong glows red.

### Verification
- [ ] All 12 microgames implemented and functional
- [ ] No two microgames feel the same
- [ ] Each is understandable from the one-word command
- [ ] The variety keeps the game from feeling repetitive through multiple cycles

---

## Step 6: Start Screen, Game Over, and Polish

### Goal
Complete the game experience.

### Start Screen
"WARIOWARE" title in 64px bold with the decorative border already cycling colors. Brief instruction: "React fast! Do what it says!" Animated preview: cycle through the command words in rapid succession as a teaser. "Press SPACE to start."

### Boss Stage (optional fun feature)
Every 12 microgames, a "BOSS STAGE" microgame appears that lasts 8-10 seconds instead of the normal 3-5. It combines elements from multiple microgames: dodge expanding circles WHILE collecting falling stars, or pop bubbles WHILE avoiding the chaser. Bold "BOSS" text appears before it. Worth 500 points.

### Game Over Screen
"GAME OVER" with final score count-up. Stats: microgames won/total, speed level reached, longest win streak. Session high score.

### Polish
- Command word text has impact animation: starts very large and snaps to normal size with screen shake
- Speed-up transitions have the border flashing rapidly
- Each microgame has a unique background color tint (very subtle, alpha 5-10) matching its theme
- Win/lose results have distinct sound-like visual patterns (win = upward starburst, lose = downward collapse)
- Timer bar urgency: when <20% remaining, the bar pulses and the border flashes

### Verification
- [ ] Start screen conveys the chaos energy of the game
- [ ] Game over shows meaningful stats
- [ ] Speed transitions feel intense and exciting
- [ ] The game is genuinely stressful and fun at higher speeds
- [ ] Boss stage (if implemented) feels like a climactic challenge
