# BREAKOUT.md — Claude Code Build Specification

## Project Summary

A Breakout/Arkanoid-style brick breaker where the UWB cursor controls the paddle position. The paddle follows the cursor's X position along the bottom of the screen. A ball bounces between the paddle, walls, and a grid of colored bricks. Break all bricks to complete a level. Power-ups fall from destroyed bricks. Classic arcade with neon style.

**File:** `breakout.html` — single self-contained HTML file with p5.js.

**Shared infrastructure:** Copy 1€ filter, WebSocket, cursor rendering, demo mode, effects from GAME_MENU.md. Include "← MENU" back button and ESC.

---

## CRITICAL INSTRUCTION

Build step-by-step. Get paddle + ball + wall bouncing working before adding bricks. Get bricks working before adding power-ups.

---

## Step 1: Paddle and Ball

### Goal
A paddle that follows cursor X, and a ball that bounces off walls and the paddle.

### Paddle
- Position: horizontally centered at cursor X, fixed ~40px from the bottom of the screen
- Size: 120px wide, 14px tall, rounded ends (use rect with large corner radius or draw as a capsule)
- Visual: bright cyan fill with a white highlight line along the top edge and a glow underneath
- Movement: paddle X lerps toward cursor X each frame (lerp factor 0.3 for smooth, responsive feel). Clamped so the paddle can't go off screen edges.

### Ball
- Size: 12px diameter circle
- Starting position: resting on top of the paddle, centered
- Launch: press space (or cursor dwells for 0.5s) to launch the ball upward at a slight random angle (70-110 degrees from horizontal)
- Speed: starts at 5 pixels/frame. Increases slightly with each brick hit (add 0.01 per brick, cap at 8)

### Ball Physics
Each frame:
- Move ball by its velocity (vx, vy)
- **Top wall:** If ball top edge touches screen top, reflect vy (vy = -vy)
- **Side walls:** If ball left/right edge touches screen sides, reflect vx
- **Paddle collision:** If ball overlaps the paddle rectangle:
  - Reflect vy upward
  - Adjust vx based on WHERE on the paddle the ball hit. Hit the left side → ball angles left. Hit the center → ball goes straight up. Hit the right side → ball angles right. Formula: `vx = (ballX - paddleX) / (paddleWidth / 2) * maxAngleSpeed` where maxAngleSpeed is ~4. This gives the player directional control.
  - Brief paddle flash (white highlight for 100ms)
- **Bottom:** If ball passes below the paddle, it's lost. Lose a life.

### Lives
Start with 3 lives. Display as dots in the top-right. Losing a ball: brief pause, screen shake, red flash. Ball respawns on the paddle. If zero lives: game over.

### Verification
- [ ] Paddle follows cursor X smoothly with slight lag
- [ ] Ball launches upward from paddle
- [ ] Ball bounces off top and side walls correctly
- [ ] Paddle hit angle varies based on impact position
- [ ] Missing the ball costs a life
- [ ] Ball respawns on paddle after lost

---

## Step 2: Brick Grid

### Goal
A grid of colored bricks at the top of the screen. Ball breaks bricks on contact.

### Brick Grid Layout
- 10 columns, 6 rows of bricks
- Each brick: ~60px wide, 20px tall, 4px gap between bricks
- Grid is centered horizontally, starts ~60px from the top of the screen
- Each row has a different color, creating a rainbow effect from top to bottom:
  Row 1 (top): red RGB(239,68,68) — worth 60 points
  Row 2: orange RGB(251,146,60) — worth 50 points
  Row 3: yellow RGB(250,204,21) — worth 40 points
  Row 4: green RGB(34,197,94) — worth 30 points
  Row 5: cyan RGB(34,211,238) — worth 20 points
  Row 6 (bottom): blue RGB(96,165,250) — worth 10 points

### Brick Rendering
Each brick has:
- Solid color fill with slight transparency (alpha ~220)
- Thin brighter highlight along the top edge (simulates 3D)
- Subtle darker shade along the bottom edge
- Very faint glow in the brick color (draw a slightly larger rectangle behind at alpha ~15)

### Brick Collision
Each frame, check if the ball overlaps any active brick. If so:
- Deactivate the brick (mark as destroyed)
- Determine which side the ball hit (compare overlap amounts on each axis) and reflect the ball's velocity accordingly (vy if hit top/bottom, vx if hit sides)
- Award points based on brick row
- Trigger destruction effects

### Brick Destruction Effects
- The brick shatters: spawn 4-6 small rectangular fragments that fly outward with random velocity and rotation, colored the same as the brick, fading over 0.5 seconds
- Brief bright flash at the brick position
- Floating score text ("+XX")
- Subtle screen shake (intensity 1, duration 50ms) — very subtle, not disruptive

### Level Complete
When all bricks are destroyed: "LEVEL CLEAR!" text, brief pause, then regenerate the grid with a new layout. Increase ball speed slightly for the next level. Restore the ball to the paddle.

### Verification
- [ ] Brick grid renders with rainbow rows
- [ ] Ball destroys bricks on contact and bounces correctly
- [ ] Destruction animation shows shattering fragments
- [ ] Points awarded per brick, higher rows worth more
- [ ] All bricks destroyed triggers level complete
- [ ] New level generates with slightly harder settings

---

## Step 3: Power-Up System

### Goal
Destroyed bricks occasionally drop power-ups that fall toward the paddle. Catching them with the paddle activates effects.

### Power-Up Drop Rate
~15% of bricks drop a power-up when destroyed. The power-up spawns at the brick's position and falls straight down at 2 pixels/frame. If it passes below the paddle without being caught, it disappears. Catching = power-up overlaps the paddle.

### Power-Up Types

**Multi-Ball (blue icon, 3 dots):** Spawns 2 additional balls from the current ball's position, angled ±30 degrees from its current direction. All balls are independent. You only lose a life when ALL balls are lost.

**Wide Paddle (green icon, horizontal arrows):** Paddle width doubles (240px) for 10 seconds. Timer bar shown below paddle.

**Laser (red icon, vertical lines):** Paddle gains two small "cannons" on its ends. Pressing space (or auto-fire every 400ms) shoots small laser bolts upward that destroy one brick each on contact. Lasts 8 seconds.

**Sticky Paddle (yellow icon, glue drop):** The ball sticks to the paddle when it hits. Press space to release it. This lets the player aim their next shot. Lasts until the ball is released 3 times.

**Extra Life (pink icon, heart):** Immediately adds one life (max 5).

**Speed Down (cyan icon, down arrow):** Reduces ball speed by 20% for 10 seconds. Useful at higher levels when ball is very fast.

### Power-Up Rendering
Each power-up is a small capsule shape (~30×18px) falling downward. It has the icon's color as a bright fill with a white symbol inside. It glows softly and rotates slowly. Make them visually distinct from brick fragments.

### Active Power-Up Indicator
Show active timed power-ups as small icon + timer bar near the top of the screen. Multiple can be active simultaneously.

### Verification
- [ ] Power-ups drop from ~15% of destroyed bricks
- [ ] Catching with paddle activates the effect
- [ ] Multi-ball creates additional independent balls
- [ ] Wide paddle visibly doubles paddle size
- [ ] Laser fires projectiles that destroy bricks
- [ ] Sticky paddle catches and holds the ball
- [ ] Extra life adds a life
- [ ] Active indicators show timers

---

## Step 4: Level Progression

### Goal
Multiple levels with different brick layouts and increasing challenge.

### Level Layouts
Design at least 5 distinct layouts. Each level should feel different:

**Level 1 — Standard:** Full 10×6 grid. Introduction level.

**Level 2 — Checkerboard:** Alternating bricks removed, creating gaps. Ball bounces through the gaps unpredictably.

**Level 3 — Diamond:** Bricks arranged in a diamond/rhombus shape. More open space.

**Level 4 — Fortress:** A thick border of bricks with a hollow center. Must break through the outer wall.

**Level 5 — Stripes:** Alternating full rows and empty rows. Fast bouncing between remaining rows.

After level 5: cycle back to level 1 layout but with harder bricks (see below).

### Hard Bricks
Starting from the second cycle (level 6+), some bricks become "hard" — they require 2 hits to destroy. Hard bricks have a visible crack after the first hit. They use a brighter, more saturated color and have a subtle shimmer effect. 10-25% of bricks are hard, increasing with cycles.

### Between Levels
Brief "LEVEL X" display (1.5 seconds) with the level layout previewed as a small diagram. Ball resets to paddle. Any active power-ups end.

### Speed Progression
Ball base speed increases by 0.3 per level. This makes later levels significantly more challenging.

### Verification
- [ ] Each level has a distinct layout
- [ ] Hard bricks take 2 hits with visible damage
- [ ] Speed increases per level
- [ ] Cycling through levels multiple times keeps getting harder

---

## Step 5: HUD, Scoring, and Screens

### Goal
Complete the game experience with polished HUD and game flow.

### HUD During Gameplay
- **Top-left:** "← MENU" back button + "LEVEL X" text
- **Top-center:** Score (large, smooth counting animation)
- **Top-right:** Lives as paddle icons or dots. High score below.
- **Below paddle:** Timer bars for any active power-ups
- **Ball count indicator:** If multi-ball is active, show "×3 BALLS" text

### Start Screen
"BREAKOUT" in 64px bold. Animated preview: a ball bouncing between invisible walls with a trail. "Move to control paddle. Break all bricks!" instruction. "Press SPACE to launch."

### Game Over Screen
Ball falls off screen for the last time. "GAME OVER" with score count-up. Stats: bricks broken, levels cleared, power-ups caught. Session high score.

### Pause Feature
Pressing P or holding cursor completely still for 3 seconds pauses the game. Everything freezes with "PAUSED" overlay. Resume by moving cursor or pressing P.

### Verification
- [ ] HUD shows all relevant info without cluttering gameplay
- [ ] Start screen is clean and inviting
- [ ] Game over shows meaningful stats
- [ ] Pause works correctly

---

## Step 6: Polish and Visual Effects

### Goal
Make the game feel like a modern neon reimagining of classic Breakout.

### Ball Trail
The ball leaves a short glowing trail behind it (last 8 positions, fading). Trail color matches the last brick the ball bounced off of, creating a color-changing effect as it breaks different bricks.

### Paddle Hit Effects
When the ball hits the paddle: brief white flash on the paddle, small particle burst upward from the impact point, subtle "thump" visual (paddle squashes slightly for 2 frames then returns).

### Brick Grid Glow
The remaining bricks collectively emit a subtle ambient glow — the more bricks remaining, the brighter the top of the screen. As bricks are cleared, the glow dims. This subconsciously rewards the player.

### Background
Very subtle animated pattern: faint concentric circles or a slow-moving grid that reacts slightly to the ball's position (nearest grid lines brighten when the ball passes). Purely atmospheric.

### Combo Bonus
Breaking multiple bricks in quick succession (ball hits 3+ bricks within 1 second without touching the paddle or walls in between) awards a combo bonus: "×2!", "×3!" etc. Each subsequent brick in the combo is worth double the previous.

### Verification
- [ ] Ball trail creates a colorful streak across the screen
- [ ] Paddle hit animation is satisfying and responsive
- [ ] Brick grid glow adds atmosphere
- [ ] Combo bonus rewards skillful angle shots
- [ ] Overall visual style reads as "neon retro arcade"
