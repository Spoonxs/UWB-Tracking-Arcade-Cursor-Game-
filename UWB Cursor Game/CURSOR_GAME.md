# CURSOR_GAME.md — Claude Code Build Specification

## Project Summary

Backup game if only 1-2 UWB tags work. A single tag maps to an on-screen cursor. The player physically walks and reaches around the UWB tracking area to play arcade-style minigames. Games cycle through rounds with increasing difficulty. If 2 tags work, enables 2-player cooperative/competitive mode.

**Tech stack:** Single HTML file. p5.js from CDN. Vanilla JavaScript. Identical infrastructure to the pose game — same WebSocket protocol, same Python bridge, same 1€ filter.

---

## CRITICAL INSTRUCTION

Build this project in sequential steps. Complete each step entirely and verify it works before moving to the next. Do NOT try to write all minigames at once. Get the framework solid first, then add minigames one at a time.

---

## Step 1: HTML Scaffold and Canvas Setup

### Goal
Create the base HTML file. Identical setup to the pose game but with a more colorful neon arcade palette.

### Requirements
- Single file called `cursor_game.html`
- Load p5.js version 1.9.0 from cdnjs.cloudflare.com
- Load "Outfit" font from Google Fonts (weights 300, 400, 600, 800, 900)
- CSS: body margin 0, overflow hidden, background #0a0a0f, font-family Outfit
- p5.js setup: full-window canvas, initialize ambient background particles
- p5.js draw: dark background, update ambient particles, "Loading..." text at center
- Handle windowResized

### Configuration Object
Define a global CONFIG at the top of the script containing:
- **WebSocket URL:** ws://localhost:8765
- **UWB bounds:** x 0-4m, y 0-3m
- **Player tag IDs:** player 1 is tag 1, player 2 is tag 2
- **Cursor visuals:** size 24px, trail length 12 positions, P1 color cyan RGB(0,210,255), P2 color magenta RGB(255,50,200)
- **Gameplay:** starting lives 3, max lives 5, difficulty scale 0.15 per round
- **Colors:** background RGB(10,10,15), green RGB(34,197,94), red RGB(239,68,68), amber RGB(245,158,11), cyan RGB(0,210,255), magenta RGB(255,50,200), lime RGB(132,255,44), orange RGB(255,140,50)
- **Demo timeout:** 3000ms

### Ambient Background Particles
~50 small white dots drifting slowly upward with slight horizontal drift. Alpha 15-50, size 1-3px. Respawn at bottom when they exit top. Run across all game states.

### Verification
- [ ] Opens in browser, dark background, no errors
- [ ] Ambient particles drift in background
- [ ] CONFIG accessible in console

---

## Step 2: Data Pipeline — Filter, WebSocket, Coordinates, Demo Mode

### Goal
Build the complete data pipeline. This reuses the exact same systems as the pose game: 1€ filter, WebSocket connection, coordinate mapping, and demo mode. Implement all four together since they depend on each other.

### One Euro Filter
Identical implementation to pose game. One filter instance per tag per axis. See Step 3 of POSE_GAME.md for algorithm details. Use minCutoff 1.0, beta 0.007, expected frequency 20Hz.

### WebSocket Connection
Connect to CONFIG.WS_URL. Parse incoming tag JSON. For each tag: map UWB coordinates to screen pixels, apply 1€ filter, update the player's data. Auto-reconnect on disconnect with 1-second delay.

### Coordinate Mapping
Same as pose game: UWB x-range maps to screen with 100px padding, Y is flipped.

### Player Data Structure
For each detected tag, maintain: screenX, screenY, a trail array of the last N positions (for the cursor trail effect), active flag, color (cyan for P1, magenta for P2), and label ("P1" or "P2").

Update the trail each frame by prepending the current position and popping the oldest if length exceeds the configured trail length.

### Demo Mode
If no WebSocket data for the timeout duration: P1 cursor follows mouse with ±3px noise applied before filtering. P2 is NOT simulated in demo — requires a real second tag. Show "DEMO" badge in top-right.

### Connection Indicator
Small dot top-left: green if connected, red if not.

### Game State Object
Create a global game object tracking: state string ("menu"/"countdown"/"playing"/"round_result"/"results"), players object, twoPlayerMode flag, score, lives, round number, current minigame index, minigame order array, minigame start timestamp, difficulty multiplier, current minigame state object (game.mini), WebSocket state, demo state, stats (minigames survived, total points), effects state (floating scores, game particles, screen shake, screen flash).

### Verification
- [ ] Demo mode activates, cursor follows mouse with smooth trail
- [ ] Connection indicator works
- [ ] 1€ filter smooths noisy input
- [ ] Trail array fills to configured length
- [ ] Auto-reconnect works

---

## Step 3: Cursor Drawing with Trail Effect

### Goal
Draw a beautiful, satisfying cursor with a glowing trail. This cursor IS the game — it needs to feel responsive and alive.

### Cursor Rendering (back to front)
1. **Trail:** Loop through the trail array from oldest to newest. Each point draws as a circle whose size decreases from cursor size to 4px, and whose alpha decreases from 180 to 0. Use the player's color at ~35% alpha. This creates a fading comet tail.

2. **Outer glow:** A soft radial gradient glow behind the cursor at 2.5x cursor size. Use the same concentric-circles-with-decreasing-alpha technique as the pose game's glow function. Max alpha ~30.

3. **Main dot:** Solid circle at cursor size with the player's color at ~220 alpha.

4. **Bright center:** Small white circle at 35% of cursor size, ~180 alpha. Gives a "light source" feel.

5. **Player label:** In 2-player mode, show "P1" or "P2" in small text above the cursor in the player's color.

### Cursor Hover Feedback
Create a helper function to check if a cursor overlaps a circular target (distance < target radius + cursor radius / 2). When hovering something interactive, draw an additional larger glow pulse using a sine wave for the radius.

### Verification
- [ ] Cursor visible in demo mode, follows mouse smoothly
- [ ] Trail creates a fading comet tail behind movement
- [ ] Glow is a soft gradient, not a hard circle
- [ ] White center dot visible
- [ ] Fast movement creates a sweeping trail
- [ ] Standing still: trail collapses, glow persists

---

## Step 4: Game State Machine and Minigame Framework

### Goal
Build the state machine and a generic framework for loading, running, and transitioning between minigames. Use a placeholder minigame to test the framework.

### State Transitions
- Menu → Countdown: space pressed. Reset all state, shuffle minigame order.
- Countdown → Playing: 3 seconds. Initialize first minigame.
- Playing → Round Result: minigame ends (success or failure).
- Round Result → Playing: 1.5 seconds. Advance to next minigame.
- Round Result → Results: if lives reach zero.
- Results → Menu: space pressed.

### Minigame Interface Contract
Every minigame must be an object with these properties:
- **name:** display string
- **description:** short text shown during intro
- **color:** RGB theme color for this minigame
- **duration:** milliseconds (or null for event-driven endings)
- **setup(difficulty):** called once when minigame starts. Initializes game.mini with all minigame-specific state. Difficulty starts at 1.0 and increases.
- **update(players, difficulty):** called every frame. Handles game logic and collision detection. Returns null to continue, or an object with done/success/points to end the minigame.
- **draw():** renders minigame objects. Cursors and HUD are drawn by the framework AFTER this.
- **getPoints():** returns point value when minigame ends by duration timeout.

### Playing State Loop
Each frame during playing state:
1. Get current minigame from the shuffled order
2. Check if duration has elapsed (adjusted by difficulty: divide by sqrt of difficulty)
3. Call the minigame's update function
4. If update returns done, call endMinigame
5. Call the minigame's draw function
6. Draw the timer bar
7. Draw cursors on top
8. Draw HUD on top of cursors

### End Minigame Logic
On success: add points to score, increment survival counter, show floating score, green flash.
On failure: decrement lives, red flash, screen shake.
If lives reach zero: go to results. Otherwise: go to round result.

### Advancing Between Minigames
After the round result's 1.5-second pause: increment the minigame index. If all minigames in the cycle have been played: increment round, increase difficulty multiplier (1 + round × 0.15), reshuffle order, reset index to 0, award a bonus life if below max. Call the next minigame's setup function and enter playing state.

### Placeholder Minigame
For testing: a minigame called "TEST" with 5-second duration that just shows "MINIGAME RUNNING" text and a frame counter. This validates the entire framework before you build real minigames.

### Timer Bar
Bottom of screen, 6px height, full width. Depletes over the adjusted duration. Color starts as the minigame's theme color, shifts to red when below 25% remaining.

### Verification
- [ ] Menu → countdown → playing → round_result loop works correctly
- [ ] Placeholder runs for 5 seconds then ends
- [ ] Lives decrement on failure
- [ ] Game over screen appears at 0 lives
- [ ] Difficulty multiplier increases after full cycle
- [ ] Timer bar visible and depleting
- [ ] Cursor draws on top of minigame content

---

## Step 5: Screen Shake, Flash, Particles, and Floating Scores

### Goal
Implement all "juice" effects. Every interaction needs satisfying visual feedback.

### Screen Shake
Triggered with an intensity (pixels) and duration (ms). Each frame during shake: compute decay based on elapsed time, apply a random translate offset scaled by intensity × decay. The shake naturally fades to zero.

### Screen Flash
Triggered with a color and duration. Draws a full-screen semi-transparent rectangle that fades from starting alpha (~120) to zero over the duration.

### Game Particle Bursts
Separate from ambient particles. An emit function creates N particles at a position with a color and max speed. Each particle gets a random angle and speed, a random size 3-8px, alpha starting at 255, and a random decay rate. Each frame: update position by velocity, apply slight gravity (vy += 0.06), slight drag (vx *= 0.99), decrease alpha by decay, shrink size. Remove when alpha reaches zero.

### Floating Scores
Array of floating text objects. Each has: position, display text ("+XX"), alpha starting at 255, upward velocity (-2.5 px/frame that decays via friction), and lifetime (~50 frames). Each frame: move up, decrease alpha proportionally. Remove when lifetime expires. Render in green at 26px.

### Verification
- [ ] Calling screen shake in console produces visible vibration that decays
- [ ] Flash creates a colored overlay that fades
- [ ] Particle burst shoots from a point with gravity and fading
- [ ] Floating scores drift up and disappear
- [ ] Rapid triggers don't stack weirdly or crash

---

## Step 6: Minigame — TAP TARGETS

### Goal
First real minigame. Glowing circles appear at random positions. Move cursor into them to pop them. Each pop earns 10 points. Duration: 10 seconds.

### Setup
Initialize with: empty targets array, spawn timer, spawn interval (1200ms / difficulty), tapped counter, max targets (4 + floor of difficulty, capped at 8), color palette (cycle through cyan, lime, orange, magenta).

Spawn 3 initial targets.

### Target Properties
Each target has: random position (with 120px margin from edges), random radius (30-55px, divided by sqrt of difficulty for harder rounds), max lifetime (2500-4000ms, divided by difficulty), birth timestamp, random color from palette, popping flag, pop start time.

### Spawn Logic
Every spawn-interval milliseconds, create a new target if below max count.

### Collision and Popping
Each frame, check every non-popping target against all active player cursors. If cursor overlaps target: set popping flag, record pop time, increment tapped counter, add 10 to score, create floating "+10" score at target position, emit 12-15 particles in the target's color.

### Expiration
Targets that exceed their max lifetime without being tapped simply disappear (no penalty).

### Drawing Targets
**Alive targets:** Outer glow in target color, stroke-only ring, semi-transparent fill. As lifetime progresses, the target slowly shrinks (70% of original size at death). When more than 70% of lifetime has elapsed, add a pulsing red urgency ring around the target.

**Popping targets:** Over 300ms, scale up to 1.6× and fade alpha to zero. Then remove.

Show "Tapped: X" counter at top center.

### End
Duration-based (10s adjusted by difficulty). Framework calls endMinigame with success=true and points = tapped × 10.

### Verification
- [ ] Targets spawn as glowing colored circles
- [ ] Moving cursor over target pops it with animation and particles
- [ ] "+10" floating score on each pop
- [ ] Targets shrink over time, nearly-expired ones pulse red
- [ ] Higher difficulty: faster spawns, smaller targets, shorter life

---

## Step 7: Minigame — DODGE

### Goal
Red obstacles fall from the top. Move cursor to avoid them. Getting hit ends the minigame as a failure. Score accumulates per half-second survived. Duration: 12 seconds.

### Setup
Initialize: empty obstacles array, spawn timer, spawn interval (700ms / difficulty), survival counter, score tick timer.

### Obstacles
Red rounded rectangles with random width (50-100px, scaled up by sqrt of difficulty), random height (18-30px), random fall speed (3-7 × difficulty), slight random rotation for visual interest.

### Spawn Logic
Every spawn-interval ms, create a new obstacle at a random X position above the screen.

### Movement and Collision
Each frame: move obstacles downward by their speed. Remove any that pass below the screen.

For collision: use rectangle-vs-circle check. Find the closest point on the rectangle to the cursor center. If distance from cursor center to that closest point is less than half the cursor size, it's a hit. A hit returns done=true, success=false.

### Scoring
Every 500ms survived, increment counter and add 5 to score.

### Drawing
Red rectangles with slight glow behind them, a bright highlight line at the top edge for 3D feel. Slight rotation per obstacle.

### Verification
- [ ] Obstacles fall from top at varying speeds
- [ ] Collision detection works — touching an obstacle ends the minigame
- [ ] Speed and frequency increase with difficulty
- [ ] Score ticks +5 every half second

---

## Step 8: Minigame — WHACK-A-MOLE

### Goal
3×3 grid. "Moles" appear in random cells for a brief time. Move cursor to the active cell to whack. +15 points per whack. Duration: 12 seconds.

### Grid Setup
9 cells arranged in a 3×3 grid, each ~130×130px with 15px gaps, centered on screen. Each cell tracks: center position, size, active flag, activated timestamp, whacked flag, whacked timestamp.

### Mole Logic
Every interval (1500ms / difficulty), activate a random inactive cell. Maximum active moles at once: 1 + floor(difficulty), capped at 3. Active moles remain for 1800ms / difficulty, then deactivate if not whacked.

### Whacking
If cursor enters an active cell: deactivate mole, set whacked flag, record timestamp, add 15 points, create floating "+15", emit 12 lime-colored particles.

### Drawing
**Inactive cells:** Very faint background rectangle (alpha ~10) with rounded corners.

**Active cells:** Glowing lime circle inside the cell with a pulsing glow effect. As lifetime progresses past 60%, add a red urgency ring.

**Whacked cells:** Brief flash animation — the cell fills with lime color and shrinks over 400ms, then clears.

### Verification
- [ ] 3×3 grid visible and centered
- [ ] Moles appear as glowing circles in random cells
- [ ] Moving cursor into active cell whacks it with particles
- [ ] Higher difficulty: shorter mole duration, more active simultaneously

---

## Step 9: Minigame — RED LIGHT GREEN LIGHT

### Goal
Screen alternates between "move" (green) and "freeze" (red) phases. Player must move their cursor from the left side to the right side. Moving during red phase resets position to start. Duration: 15 seconds.

### Phase Logic
Green phases last 2-4 seconds (divided by difficulty). Red phases last 1.5-2.5 seconds. Phases alternate with random durations within these ranges.

### Player Progress
Track each player's progress as an X position from start line (120px from left) to finish line (120px from right). During green phases: map the cursor's actual screen X position to progress — moving right in the room moves progress right. During red phases: track cursor movement delta per frame. If the delta exceeds 6 pixels, the player is "caught" — reset their progress to the start line, brief red flash and screen shake.

### Win Condition
If any player's progress reaches the finish line: return done=true, success=true, 50 points.

### Drawing
**Background tint:** Entire screen gets a subtle green or red wash (alpha ~8-15) based on current phase.

**Start/finish lines:** Vertical lines at start and finish X positions, white at low alpha.

**Phase text:** Large "GO!" in green or "FREEZE!" in red, centered near the top.

**Progress markers:** Each player's progress shown as a glowing dot in their color moving along the center Y of the screen.

**Caught flash:** Brief red overlay (300ms) when a player is caught moving during red.

### Verification
- [ ] Green and red phases alternate with visible text and background color
- [ ] Moving during green advances progress
- [ ] Moving during red resets to start with shake feedback
- [ ] Reaching finish ends with success
- [ ] Higher difficulty: shorter green phases

---

## Step 10: Minigame — COLLECT & AVOID

### Goal
Green coins and red bombs spawn and drift around. Collect green for points, avoid red or lose the minigame. Duration: 12 seconds.

### Spawning
Every 600ms / difficulty, spawn an item. 70% chance of coin (green), 30% chance of bomb (red). At higher difficulty, bomb ratio increases toward 50%.

### Item Properties
Each item has: position, radius (~20-30px), velocity (random direction, speed 1-3 × sqrt of difficulty), color, type (coin or bomb), lifetime (5 seconds then despawn if untouched).

Items drift with their velocity and bounce off screen edges (reverse the relevant velocity component on impact).

### Collection/Hit Detection
Check cursor overlap against all items each frame.

**Coin collected:** +10 points, remove item, floating "+10", green particle burst.
**Bomb touched:** Return done=true, success=false. Screen shake, red flash.

### Drawing
**Coins:** Green circles with soft glow, slight bobbing via sine wave on Y position.
**Bombs:** Red circles with an X pattern drawn inside (two crossed lines), red glow, pulsing danger ring.

Both cursors can interact in 2-player mode (cooperative — both collect/trigger).

### Verification
- [ ] Green and red items clearly distinguishable
- [ ] Collecting green gives +10 with particles
- [ ] Touching red ends minigame with failure
- [ ] Items bounce off screen edges
- [ ] Higher difficulty: more bombs, faster movement

---

## Step 11: Minigame — TRACE THE PATH

### Goal
A glowing path appears on screen. Player must trace it with their cursor from start to end. Score based on percentage completed. Duration: 10 seconds.

### Path Generation
Generate a smooth curved path as an array of ~100 points. Use 4-6 random control points spread across the screen (with edge padding), and interpolate between them using bezier curves or catmull-rom splines. The path should go generally from left to right or top to bottom.

Mark the first point as "start" (draw a green circle) and the last as "finish" (draw a checkered flag or bright marker).

### Tracing Logic
Track a "current target index" starting at 0. Each frame, if the cursor is within 30px of the point at the current target index, advance the index. The player must follow the path in order — they can't skip ahead. Progress percentage = current index / total points.

### Drawing
**Path:** Draw the full path as a thick semi-transparent line (alpha ~40, width ~20px) connecting all points.

**Completed portion:** Redraw the path from start to current target index in bright green (alpha ~180).

**Current target:** Draw a pulsing glow at the current target point so the player can see where to go next.

**Progress indicator:** Show "XX%" at top center.

### End
When duration expires, return points proportional to completion: floor(progress × 80). Full completion = 80 points.

### Verification
- [ ] Path is visible as a smooth curve
- [ ] Following the path turns the completed portion green
- [ ] Current target has a clear visual indicator
- [ ] Score reflects completion percentage

---

## Step 12: Menu and Results Screens

### Goal
Polished menu and results screens.

### Menu Screen
- Title: "TAG GAMES" in 64px bold white
- Subtitle: "Move your body to play!" in 18px light, 50% opacity
- Tag status: "X tag(s) connected" in green, or "Demo mode — use mouse" in amber
- If 2 tags detected: "2 PLAYER MODE AVAILABLE" in magenta. Press "2" key to toggle.
- "Press SPACE to start" pulsing (opacity 0.3 to 0.8 via sine)
- Show live cursor on menu if tags streaming (proves tracking works)
- Ambient particles running in background

### Results Screen
- "GAME OVER" in 52px
- Score in 72px with count-up animation from 0 to final over 1.5 seconds, ease-out cubic
- Stats: "Minigames survived: X", "Rounds completed: X"
- Lives display: show colored dots (green for remaining at death, dark gray for lost)
- "Press SPACE to play again" pulsing

### State Reset on Replay
Clear everything: score, lives back to starting, round to 0, difficulty to 1.0, minigame index to 0, all counters, all effects. Reshuffle minigame order.

### Verification
- [ ] Menu looks clean with title, status, instructions
- [ ] Two-player toggle works if 2 tags detected
- [ ] Results show meaningful, accurate stats
- [ ] Score count-up animation is smooth
- [ ] Replay resets cleanly

---

## Step 13: HUD During Gameplay

### Goal
Show persistent game info overlaid during minigames.

### Top Bar
- **Left:** Current minigame name in its theme color (18px bold)
- **Center:** Score in 32px bold (use monospace or tabular figures so digits don't shift)
- **Right:** Lives as 10px dots with 6px gaps — green for remaining, dark gray for lost

### Timer Bar
Bottom of screen, 6px height, full width. Depletes over the minigame's adjusted duration. Color starts as the minigame's theme color, shifts to amber at 50%, red at 25%.

### Minigame Intro Overlay
Between minigames, during the round_result pause: show the UPCOMING minigame's name in 40px centered text with its description below in 16px. Background gets a subtle tint of the minigame's theme color (alpha ~8). Displayed for 1.5 seconds before gameplay begins.

### Round/Difficulty Indicator
Small "Round X" text in bottom-left corner, 12px, 40% opacity.

### Verification
- [ ] Lives dots update correctly on damage and recovery
- [ ] Score updates in real-time during minigames
- [ ] Minigame name visible in correct theme color
- [ ] Timer bar depletes correctly
- [ ] Intro overlay shows upcoming minigame name

---

## Step 14: Difficulty System and Balancing

### Goal
Make difficulty scaling feel fair, noticeable, and fun across all minigames.

### Difficulty Multiplier
`difficulty = 1 + round × 0.15` where round increments after each complete cycle through all minigames.

### Per-Minigame Scaling

**TAP TARGETS:** Spawn interval divides by difficulty. Target radius divides by sqrt(difficulty). Target lifetime divides by difficulty. Max targets increases with difficulty.

**DODGE:** Obstacle speed multiplies by difficulty. Spawn interval divides by difficulty. Obstacle width scales up by sqrt(difficulty).

**WHACK-A-MOLE:** Mole display duration divides by difficulty. Max active moles increases. Spawn interval decreases.

**RED LIGHT GREEN LIGHT:** Green phase duration divides by difficulty. Red phases stay the same or get slightly longer.

**COLLECT & AVOID:** Bomb ratio increases toward 50%. Item speed multiplies by sqrt(difficulty). Spawn rate increases.

**TRACE THE PATH:** Path gets longer (more control points). Could add more curves or tighter turns.

### Duration Scaling
All minigame durations divide by sqrt(difficulty), NOT raw difficulty. This prevents durations from becoming impossibly short at high rounds.

### Life Recovery
After each full cycle (all minigames played once), award +1 life if below max (5). This extends runs and feels generous.

### Balance Targets
- Round 1: easy, approachable, learn the mechanics
- Round 3+: noticeably harder, requires focus
- Round 5+: challenging but not impossible
- No minigame should ever become literally unbeatable

### Verification
- [ ] Round 1 feels welcoming
- [ ] Round 3+ is noticeably harder
- [ ] No minigame becomes impossible
- [ ] Life recovery extends runs meaningfully

---

## Step 15: Polish and Final Integration

### Goal
Final visual polish, edge case handling, and integration testing.

### Polish Items

**Cursor hover feedback:** When cursor overlaps an interactive object in any minigame, the cursor should pulse larger and brighter. Each minigame should call the hover check for relevant objects.

**Background grid:** Subtle 60px grid lines at alpha 8, drawn behind everything. Adds depth.

**Smooth score counter:** Display score lerps toward actual score each frame instead of jumping instantly.

**Keyboard shortcuts:** Space=start/restart, D=toggle demo, R=reset to menu, 2=toggle two-player on menu.

**Two-player cursor distinction:** P1 has cyan glow/trail, P2 has magenta. Different trail opacity so they're easy to tell apart even when overlapping.

**Minigame background tint:** During gameplay, the background gets a very subtle color wash matching the minigame's theme color (alpha 5-10). Changes between minigames.

**Optional sound via Tone.js CDN:** Pop/collect = bright synth blip, hit/damage = low buzz + noise, whack = punchy thud, timer warning = subtle tick below 25%. All optional and wrapped in try/catch.

### Final Test Protocol
1. Open game — menu with particles
2. Demo mode activates — cursor follows mouse
3. Space — countdown 3-2-1
4. First minigame loads with name overlay
5. Play through each minigame type — scoring, effects, and feedback all work
6. Intentionally fail 3 times — game over screen appears
7. Space — fresh restart with zero leftover state
8. Console: zero errors, game object inspectable
9. Play 2+ full cycles to verify difficulty ramp
10. Verify life recovery after completing a full cycle

### Verification
- [ ] Complete playthrough with no crashes or console errors
- [ ] All 6 minigames function correctly
- [ ] Score is accurate across all minigames
- [ ] Lives system works (damage, game over, recovery)
- [ ] Difficulty ramp is noticeable but fair
- [ ] All effects fire correctly (shake, flash, particles, floating scores)
- [ ] Game is genuinely fun to play
