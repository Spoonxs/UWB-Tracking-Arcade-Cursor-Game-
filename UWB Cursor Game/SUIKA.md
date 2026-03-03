# SUIKA.md — Claude Code Build Specification

## Project Summary

A Suika (Watermelon) game controlled by UWB cursor. The player moves their cursor left/right to aim, then drops a fruit. Fruits fall into a container with physics (gravity, bouncing, rolling). When two identical fruits touch, they merge into the next larger fruit with a satisfying pop effect. Score by merging. Game over when any fruit crosses the top boundary line.

**File:** `suika.html` — single self-contained HTML file with p5.js.

**Shared infrastructure:** Copy the 1€ filter, WebSocket, cursor rendering, demo mode, ambient particles, and screen effects from GAME_MENU.md into this file. Include the "← MENU" back button and ESC key handler.

---

## CRITICAL INSTRUCTION

Build step-by-step. The physics are the hardest part — get them working with just 2-3 fruit types before adding all 11.

---

## Step 1: Container and Drop Zone

### Goal
Draw the game container and the cursor-controlled drop aim indicator.

### Container
A tall rounded rectangle centered on screen. Approximately 400px wide and 550px tall. The container has:
- Thick walls drawn as rounded rectangle strokes (3px, white at 30% alpha)
- A subtle inner glow along the walls (very faint, adds depth)
- The bottom and side walls are solid boundaries for physics
- A dashed "danger line" near the top (~80px from top of container). If any fruit's center crosses above this line AND has settled (velocity near zero), the game is over.

### Drop Zone
Above the container, the player's cursor X position controls where the next fruit will drop. Draw:
- A vertical dashed guide line from the cursor down to the container opening
- The "next fruit" preview at the cursor position (shows what fruit will drop next)
- The fruit gently follows the cursor X, clamped to the container width

### Queued Fruit
Show a small "NEXT" label in the top-right corner of the screen with a preview of the fruit that comes AFTER the current one. This lets players plan ahead.

### Verification
- [ ] Container visible, centered, with clear walls
- [ ] Cursor controls drop position horizontally
- [ ] Guide line shows where fruit will land
- [ ] Next fruit preview visible at cursor and in queue display

---

## Step 2: Fruit Types and Rendering

### Goal
Define the fruit hierarchy and draw each fruit type as a beautiful procedural circle (no images needed).

### Fruit Hierarchy (11 types, smallest to largest)
1. **Cherry** — radius 16px, color #FF6B6B (warm red)
2. **Strawberry** — radius 22px, color #FF8E8E (pink-red)
3. **Grape** — radius 28px, color #B388FF (purple)
4. **Dekopon** — radius 34px, color #FFB74D (orange)
5. **Orange** — radius 40px, color #FFA726 (deep orange)
6. **Apple** — radius 48px, color #EF5350 (red)
7. **Pear** — radius 56px, color #AED581 (light green)
8. **Peach** — radius 64px, color #F48FB1 (pink)
9. **Pineapple** — radius 72px, color #FFD54F (gold)
10. **Melon** — radius 82px, color #81C784 (green)
11. **Watermelon** — radius 94px, color #66BB6A (dark green) with darker stripes

### Fruit Rendering
Each fruit is a circle with layered visual treatment:
- **Base fill:** The fruit's color at full opacity
- **Inner gradient:** A lighter highlight in the upper-left quadrant (draw a smaller semi-transparent white ellipse offset up-left) to simulate 3D shading
- **Outline:** Slightly darker version of the fruit color, 2px stroke
- **Face (optional fun touch):** Two small dot eyes and a tiny curved mouth. Simple and cute. Makes the game more charming.
- **Number label:** Small text showing the fruit's tier number (1-11) at center, semi-transparent. Helps players learn the merge order.

### Verification
- [ ] All 11 fruit types render as distinct colored circles
- [ ] Size progression is visually clear (cherry is tiny, watermelon is huge)
- [ ] 3D shading makes them look like spheres, not flat circles
- [ ] Each fruit is easily distinguishable at a glance

---

## Step 3: Basic Physics — Gravity and Container Collision

### Goal
Implement gravity, container wall collision, and fruit-to-floor/wall bouncing. Start with just dropping fruits — no merging yet.

### Physics Model
Each fruit is a circle body with: x, y (center position), vx, vy (velocity), radius, mass (proportional to radius squared), and angular velocity for visual rotation.

### Gravity
Each frame, add gravity to vy: `vy += 0.4` (tune this for feel — should feel weighty but not sluggish).

### Container Collision
Check each fruit against the container walls each frame:
- **Bottom wall:** If fruit center + radius > container bottom, push fruit up so it sits on the surface, multiply vy by -0.3 (bounce with energy loss), apply friction to vx (multiply by 0.95)
- **Left wall:** If fruit center - radius < container left, push right, multiply vx by -0.3
- **Right wall:** If fruit center + radius > container right, push left, multiply vx by -0.3

### Damping
Apply velocity damping each frame: multiply both vx and vy by 0.998. This prevents infinite bouncing. When velocity magnitude drops below 0.1, set it to zero (fruit has settled).

### Drop Mechanic
When the player clicks (or cursor dwells on a "drop zone" area for 0.3 seconds, or presses space), release the current fruit at the cursor's X position, at the top of the container. The fruit starts with vy=0 and falls under gravity.

After dropping, there should be a brief cooldown (~500ms) before the next fruit appears at the cursor. This prevents spam-dropping.

The dropped fruit type should be randomly chosen from the first 5 tiers (cherry through orange). The next queued fruit is also random from the first 5.

### Verification
- [ ] Dropping a fruit makes it fall and bounce in the container
- [ ] Fruits settle on the floor and stack on each other
- [ ] Wall collisions prevent fruits from escaping
- [ ] Bounce has energy loss (doesn't bounce forever)
- [ ] Drop cooldown prevents spam

---

## Step 4: Circle-Circle Collision (Fruit Stacking)

### Goal
Make fruits collide with each other physically so they stack, roll, and push each other around.

### Collision Detection
Each frame, check every pair of fruits. If the distance between two fruit centers is less than the sum of their radii, they are overlapping.

### Collision Response
When two fruits overlap:
1. Calculate the overlap distance: `overlap = (r1 + r2) - distance`
2. Calculate the collision normal: unit vector from center1 to center2
3. Separate the fruits: push each fruit apart along the normal by half the overlap (or proportional to mass)
4. Calculate relative velocity along the collision normal
5. Apply impulse: redistribute velocity along the normal with a restitution coefficient of ~0.3 (moderate bounciness)
6. Apply a small friction component perpendicular to the normal

### Optimization
With many fruits, checking every pair is O(n²). For this game with max ~30-40 fruits on screen, this is fine. No spatial partitioning needed. But do skip pairs where both fruits have zero velocity (settled).

### Verification
- [ ] Fruits stack on each other without overlapping
- [ ] Pushing a fruit into others causes them to move
- [ ] Fruits roll and settle into natural resting positions
- [ ] No fruits clip through each other or the walls

---

## Step 5: Merging Logic

### Goal
When two fruits of the same type touch, they merge into the next larger type with a satisfying visual effect.

### Merge Detection
During the circle-circle collision check in Step 4: if two overlapping fruits are the same type AND neither is currently in a merge animation, trigger a merge.

### Merge Process
1. Mark both fruits as "merging" so they can't trigger additional merges
2. Calculate the merge position: midpoint between the two fruit centers
3. Remove both original fruits from the physics simulation
4. Create a new fruit of the next tier at the merge position
5. Give the new fruit a small random velocity (slight pop upward: vy = -2 to -4)
6. Award score: each tier is worth more points. Simple formula: tier × tier × 10 (cherry=10, strawberry=40, grape=90, etc.)
7. Trigger merge visual effects

### Watermelon (Tier 11) Special Case
If two watermelons merge, they simply disappear (score bonus of 2000 points) with an extra-large particle explosion. There is no tier 12.

### Merge Visual Effects
- Particle burst: 20-30 particles in the merged fruit's color, radiating outward from merge point
- Brief screen shake (intensity 4, duration 200ms)
- Floating score text at the merge position
- The new fruit spawns at slightly smaller scale and quickly pops to full size (scale 0.5 → 1.0 over 200ms) — a satisfying "pop into existence" feel
- Brief flash: a white circle at the merge point that rapidly expands and fades (radius 0 → merged fruit radius × 2, alpha 200 → 0, over 300ms)

### Chain Reactions
A newly spawned fruit from a merge can immediately collide with another fruit of its same type, triggering another merge. This should happen naturally from the physics — no special code needed. Chain merges are the most satisfying part of the game.

### Verification
- [ ] Two same-type fruits touching triggers a merge
- [ ] Merged fruit is one tier larger, appears at midpoint
- [ ] Particle burst and pop animation play on merge
- [ ] Score awarded correctly
- [ ] Chain reactions happen naturally when a new fruit lands next to matching ones
- [ ] Two watermelons merging awards bonus and they disappear

---

## Step 6: Game Over Detection

### Goal
End the game when fruits stack too high.

### Danger Line
A horizontal dashed line drawn near the top of the container (~80px below the container opening). Color: red at low alpha (~30), pulsing when danger is near.

### Detection Logic
Each frame, check if any fruit meets ALL of these conditions:
- Its center Y position is above the danger line
- Its velocity magnitude is below 0.5 (it has settled, not just passing through while falling)
- It has existed for at least 1 second (prevents instant game-over from a just-dropped fruit)

When detected: freeze physics, show "GAME OVER" overlay, display final score, show "Press SPACE to retry" or hover-to-retry button.

### Danger Warning
When any fruit is within 50px of the danger line AND has low velocity: make the danger line pulse red more intensely, add a subtle red tint to the top of the container, optionally play a warning sound.

### Verification
- [ ] Game ends when settled fruit crosses the line
- [ ] Danger line pulses when fruits get close
- [ ] Falling fruits don't trigger false game-over
- [ ] Game over overlay shows score and retry option

---

## Step 7: HUD and Score Display

### Goal
Show score, current fruit, next fruit, and game state info.

### Layout
- **Top-left:** "← MENU" back button (from shared system)
- **Top-center:** Score in large text (36px bold). Smooth counting animation (lerps toward real value).
- **Top-right:** "NEXT" label with small preview of the queued fruit
- **At cursor:** The current fruit to be dropped, following cursor X
- **Bottom:** Connection status and demo indicator

### High Score
Store the session high score in a variable (resets on page reload). Display "BEST: XXXX" in small text below the current score if the player has played at least once.

### Merge Counter
Small text showing total merges performed this game. Optional but satisfying to see.

### Verification
- [ ] Score updates on merges with smooth animation
- [ ] Next fruit preview accurate
- [ ] High score tracks across retries within session

---

## Step 8: Polish and Feel

### Goal
Make the game feel satisfying and complete.

### Visual Polish
- **Container background:** Very subtle grid pattern or gradient inside the container (dark, not distracting)
- **Fruit shadows:** Each fruit casts a small, soft shadow below it (dark ellipse offset downward and stretched wider, very low alpha)
- **Settle particles:** When a fruit's velocity drops below threshold (settles), emit 3-4 tiny particles at its base. Subtle "dust" effect.
- **Merge combo text:** If a chain reaction occurs (merge triggers another merge within 500ms), show "COMBO ×2!", "COMBO ×3!" etc. in increasingly large/bright text

### Drop Input Options
Support multiple drop methods since UWB doesn't have a "click":
- **Dwell drop:** Cursor stays within a 20px zone for 0.5 seconds → auto-drop. Show a circular progress fill around the cursor during the dwell.
- **Keyboard:** Space bar drops the fruit
- **Click/tap:** For mouse/touch users

### Start Screen
Before gameplay: show "SUIKA" title, brief instructions ("Move to aim, hold still to drop. Match fruits to merge!"), "Press SPACE or hold still to start". Show the fruit hierarchy as a visual reference (all 11 fruits in a row at the bottom, smallest to largest, with names).

### Verification
- [ ] Dwell-drop works: holding cursor still drops after 0.5s with progress indicator
- [ ] Chain combo text appears for multi-merges
- [ ] Fruit shadows add depth
- [ ] Start screen shows fruit hierarchy reference
- [ ] Game feels satisfying: drops are weighty, merges pop, physics feel natural
