"""
UWB Position Visualizer
=======================
Listens for UDP packets from the ESP32 tag containing "x,y,z" position data
and displays a square on screen representing the tag's position.

Usage:
  1. Set UDP_PORT below to match UDP_TARGET_PORT in tag.ino (default 9000)
  2. Set WIFI credentials and UDP_TARGET_IP in tag.ino to your PC's IP
  3. Run: python visualizer.py
  4. Power on the ESP32 tag — the square should start moving

Controls:
  - V to cycle view: XY (top-down) / XZ (front) / YZ (side) / 3D
  - C to toggle clamping (keeps position bounded to world space)
  - Arrow keys to rotate 3D view
  - Z to zero position
  - R to reset trail / packet counter
  - ESC or close window to quit
"""

import socket
import threading
import pygame
import sys
import time
import math

# ============================================================
#  CONFIGURATION
# ============================================================

UDP_PORT = 9000           # Must match UDP_TARGET_PORT in tag.ino
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800

# Real-world bounds to map onto the window (meters)
WORLD_X_MIN = -0.5
WORLD_X_MAX = 2.0
WORLD_Y_MIN = -0.5
WORLD_Y_MAX = 2.0
WORLD_Z_MIN = -0.5
WORLD_Z_MAX = 2.0

SQUARE_SIZE = 30
BG_COLOR = (30, 30, 30)
GRID_COLOR = (60, 60, 60)
TEXT_COLOR = (200, 200, 200)
ANCHOR_COLOR = (100, 100, 255)
WIRE_COLOR = (80, 80, 80)
AXIS_COLORS = [(255, 80, 80), (80, 255, 80), (80, 80, 255)]  # X=red, Y=green, Z=blue

# ============================================================
#  VIEW MODES
# ============================================================

VIEW_XY = 0
VIEW_XZ = 1
VIEW_YZ = 2
VIEW_3D = 3

VIEW_NAMES = ["XY (top-down)", "XZ (front)", "YZ (side)", "3D"]
NUM_VIEWS = 4

# For 2D views: (horizontal axis, vertical axis, depth axis)
VIEW_AXES = [
    (0, 1, 2),  # XY
    (0, 2, 1),  # XZ
    (1, 2, 0),  # YZ
]

VIEW_H_LABELS = ["X", "X", "Y"]
VIEW_V_LABELS = ["Y", "Z", "Z"]
VIEW_D_LABELS = ["Z", "Y", "X"]

WORLD_MINS = [WORLD_X_MIN, WORLD_Y_MIN, WORLD_Z_MIN]
WORLD_MAXS = [WORLD_X_MAX, WORLD_Y_MAX, WORLD_Z_MAX]

# ============================================================
#  SHARED STATE
# ============================================================

latest_position = [0.0, 0.0, 0.0]
position_lock = threading.Lock()
last_update_time = 0.0
packet_count = 0

# ============================================================
#  UDP LISTENER (runs in background thread)
# ============================================================

def udp_listener():
    global latest_position, last_update_time, packet_count

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(1.0)

    print(f"[UDP] Listening on port {UDP_PORT}...")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8").strip()

            parts = msg.split(",")
            if len(parts) == 3:
                x = float(parts[0])
                y = float(parts[1])
                z = float(parts[2])

                with position_lock:
                    latest_position = [x, y, z]
                    last_update_time = time.time()
                    packet_count += 1

        except socket.timeout:
            continue
        except Exception as e:
            print(f"[UDP] Error: {e}")

# ============================================================
#  2D COORDINATE MAPPING
# ============================================================

def world_to_screen(wh, wv, view_mode):
    """Map two real-world axes to screen pixels based on current view."""
    h_axis, v_axis, _ = VIEW_AXES[view_mode]
    h_min, h_max = WORLD_MINS[h_axis], WORLD_MAXS[h_axis]
    v_min, v_max = WORLD_MINS[v_axis], WORLD_MAXS[v_axis]

    sx = int((wh - h_min) / (h_max - h_min) * WINDOW_WIDTH)
    sy = int((1.0 - (wv - v_min) / (v_max - v_min)) * WINDOW_HEIGHT)
    return sx, sy

def depth_to_color(depth, view_mode):
    """Map the depth axis value to a color: blue (low) to red (high)."""
    _, _, d_axis = VIEW_AXES[view_mode]
    d_min, d_max = WORLD_MINS[d_axis], WORLD_MAXS[d_axis]
    t = max(0.0, min(1.0, (depth - d_min) / (d_max - d_min)))
    r = int(50 + 205 * t)
    g = int(200 * (1.0 - t))
    b = int(50 + 205 * (1.0 - t))
    return (r, g, b)

# ============================================================
#  3D PROJECTION
# ============================================================

def project_3d(x, y, z, angle_x, angle_y, scale, cx, cy):
    """Project a 3D point onto 2D screen using rotation + perspective."""
    # Center the scene around the middle of the world
    wx = (WORLD_X_MIN + WORLD_X_MAX) / 2.0
    wy = (WORLD_Y_MIN + WORLD_Y_MAX) / 2.0
    wz = (WORLD_Z_MIN + WORLD_Z_MAX) / 2.0
    px = x - wx
    py = y - wy
    pz = z - wz

    # Rotate around Z axis (left/right arrow) — yaw
    cos_z = math.cos(angle_y)
    sin_z = math.sin(angle_y)
    temp_x = px * cos_z - py * sin_z
    temp_y = px * sin_z + py * cos_z

    # Rotate around X axis (up/down arrow) — pitch
    cos_x = math.cos(angle_x)
    sin_x = math.sin(angle_x)
    rx = temp_x
    ry = temp_y * cos_x - pz * sin_x
    rz = temp_y * sin_x + pz * cos_x

    # Simple perspective
    dist = 6.0
    persp = dist / (dist + rz) if (dist + rz) > 0.5 else dist / 0.5

    sx = int(cx + rx * scale * persp)
    sy = int(cy - ry * scale * persp)  # Y flipped (screen Y is down)

    return sx, sy, rz

def draw_3d_view(screen, font, anchor_positions, pos, trail_3d, angle_x, angle_y):
    """Draw the full 3D scene."""
    scale = 200.0
    cx = WINDOW_WIDTH // 2
    cy = WINDOW_HEIGHT // 2

    # Draw wireframe cube edges (the bounding box of the anchor space)
    cube_corners = [
        (0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (0.0, 1.5, 0.0), (1.5, 1.5, 0.0),
        (0.0, 0.0, 1.5), (1.5, 0.0, 1.5), (0.0, 1.5, 1.5), (1.5, 1.5, 1.5),
    ]
    cube_edges = [
        (0,1), (0,2), (1,3), (2,3),  # bottom face
        (4,5), (4,6), (5,7), (6,7),  # top face
        (0,4), (1,5), (2,6), (3,7),  # vertical edges
    ]

    projected_corners = []
    for c in cube_corners:
        sx, sy, _ = project_3d(c[0], c[1], c[2], angle_x, angle_y, scale, cx, cy)
        projected_corners.append((sx, sy))

    for i, j in cube_edges:
        pygame.draw.line(screen, WIRE_COLOR, projected_corners[i], projected_corners[j], 1)

    # Draw axis lines from origin (thicker, colored)
    origin_s = project_3d(0, 0, 0, angle_x, angle_y, scale, cx, cy)
    axis_ends = [(2.0, 0, 0), (0, 2.0, 0), (0, 0, 2.0)]
    axis_labels = ["X", "Y", "Z"]
    for idx, (ax, ay, az) in enumerate(axis_ends):
        end_s = project_3d(ax, ay, az, angle_x, angle_y, scale, cx, cy)
        pygame.draw.line(screen, AXIS_COLORS[idx],
                         (origin_s[0], origin_s[1]),
                         (end_s[0], end_s[1]), 2)
        label = font.render(axis_labels[idx], True, AXIS_COLORS[idx])
        screen.blit(label, (end_s[0] + 5, end_s[1] - 8))

    # Draw ground grid lines
    for i in range(3):  # 0m, 0.75m, 1.5m
        v = i * 0.75
        # Lines along X
        p1 = project_3d(0, v, 0, angle_x, angle_y, scale, cx, cy)
        p2 = project_3d(1.5, v, 0, angle_x, angle_y, scale, cx, cy)
        pygame.draw.line(screen, (50, 50, 50), (p1[0], p1[1]), (p2[0], p2[1]), 1)
        # Lines along Y
        p1 = project_3d(v, 0, 0, angle_x, angle_y, scale, cx, cy)
        p2 = project_3d(v, 1.5, 0, angle_x, angle_y, scale, cx, cy)
        pygame.draw.line(screen, (50, 50, 50), (p1[0], p1[1]), (p2[0], p2[1]), 1)

    # Draw trail
    for i, (tx, ty, tz, tc) in enumerate(trail_3d):
        alpha = int(50 + 150 * (i / max(len(trail_3d), 1)))
        fade = (tc[0] * alpha // 255, tc[1] * alpha // 255, tc[2] * alpha // 255)
        tsx, tsy, _ = project_3d(tx, ty, tz, angle_x, angle_y, scale, cx, cy)
        pygame.draw.circle(screen, fade, (tsx, tsy), 2)

    # Draw anchors
    for i, ap in enumerate(anchor_positions):
        asx, asy, _ = project_3d(ap[0], ap[1], ap[2], angle_x, angle_y, scale, cx, cy)
        size = 8
        points = [(asx, asy - size), (asx + size, asy), (asx, asy + size), (asx - size, asy)]
        pygame.draw.polygon(screen, ANCHOR_COLOR, points)
        pygame.draw.polygon(screen, TEXT_COLOR, points, 1)
        label = font.render(f"A{i}", True, ANCHOR_COLOR)
        screen.blit(label, (asx + 12, asy - 8))

    # Draw tag position
    psx, psy, pdepth = project_3d(pos[0], pos[1], pos[2], angle_x, angle_y, scale, cx, cy)

    # Drop line from tag down to ground plane (Z=0)
    gsx, gsy, _ = project_3d(pos[0], pos[1], 0, angle_x, angle_y, scale, cx, cy)
    pygame.draw.line(screen, (100, 100, 100), (psx, psy), (gsx, gsy), 1)
    pygame.draw.circle(screen, (100, 100, 100), (gsx, gsy), 3)  # ground shadow

    # Tag square
    z_frac = max(0.0, min(1.0, (pos[2] - WORLD_Z_MIN) / (WORLD_Z_MAX - WORLD_Z_MIN)))
    tag_color = (int(50 + 205 * z_frac), int(200 * (1.0 - z_frac)), int(50 + 205 * (1.0 - z_frac)))
    half = SQUARE_SIZE // 2
    pygame.draw.rect(screen, tag_color, (psx - half, psy - half, SQUARE_SIZE, SQUARE_SIZE))
    pygame.draw.rect(screen, TEXT_COLOR, (psx - half, psy - half, SQUARE_SIZE, SQUARE_SIZE), 2)

    return tag_color

# ============================================================
#  2D DRAW HELPERS
# ============================================================

def draw_grid(screen, font, view_mode):
    """Draw a reference grid with meter markings."""
    h_axis, v_axis, _ = VIEW_AXES[view_mode]
    h_min, h_max = WORLD_MINS[h_axis], WORLD_MAXS[h_axis]
    v_min, v_max = WORLD_MINS[v_axis], WORLD_MAXS[v_axis]
    h_label = VIEW_H_LABELS[view_mode]
    v_label = VIEW_V_LABELS[view_mode]

    for m in range(int(h_min), int(h_max) + 1):
        sx, _ = world_to_screen(m, 0, view_mode)
        if 0 <= sx <= WINDOW_WIDTH:
            pygame.draw.line(screen, GRID_COLOR, (sx, 0), (sx, WINDOW_HEIGHT))
            label = font.render(f"{h_label}={m}m", True, GRID_COLOR)
            screen.blit(label, (sx + 3, WINDOW_HEIGHT - 20))

    for m in range(int(v_min), int(v_max) + 1):
        _, sy = world_to_screen(0, m, view_mode)
        if 0 <= sy <= WINDOW_HEIGHT:
            pygame.draw.line(screen, GRID_COLOR, (0, sy), (WINDOW_WIDTH, sy))
            label = font.render(f"{v_label}={m}m", True, GRID_COLOR)
            screen.blit(label, (5, sy + 3))

def draw_anchors(screen, font, anchor_positions, view_mode):
    """Draw anchor positions as labeled diamonds."""
    h_axis, v_axis, _ = VIEW_AXES[view_mode]

    for i, pos in enumerate(anchor_positions):
        ah = pos[h_axis]
        av = pos[v_axis]
        sx, sy = world_to_screen(ah, av, view_mode)
        size = 8
        points = [(sx, sy - size), (sx + size, sy), (sx, sy + size), (sx - size, sy)]
        pygame.draw.polygon(screen, ANCHOR_COLOR, points)
        pygame.draw.polygon(screen, TEXT_COLOR, points, 1)
        label = font.render(f"A{i}", True, ANCHOR_COLOR)
        screen.blit(label, (sx + 12, sy - 8))

def clamp_position(pos):
    """Clamp position to world bounds."""
    return [
        max(WORLD_X_MIN, min(WORLD_X_MAX, pos[0])),
        max(WORLD_Y_MIN, min(WORLD_Y_MAX, pos[1])),
        max(WORLD_Z_MIN, min(WORLD_Z_MAX, pos[2])),
    ]

# ============================================================
#  MAIN
# ============================================================

def main():
    global packet_count

    # Anchor positions as [x, y, z] — must match tag.ino layout
    anchor_positions = [
        [0.0, 0.0, 0.0],   # A0 - origin
        [1.5, 0.0, 0.0],   # A1 - X axis
        [0.0, 1.5, 0.0],   # A2 - Y axis
        [0.0, 0.0, 1.5],   # A3 - Z axis
        [1.5, 1.5, 0.0],   # A4 - XY corner
        [1.5, 1.5, 1.5],   # A5 - opposite corner
    ]

    # Start UDP listener thread
    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()

    # Init pygame
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("UWB Position Visualizer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 16)

    trail = []          # 2D trail: (sx, sy, color)
    trail_3d = []       # 3D trail: (x, y, z, color)
    max_trail = 100
    view_mode = VIEW_XY
    zero_offset = [0.0, 0.0, 0.0]
    clamp_enabled = False

    # 3D camera angles — Z axis pointing up at startup
    angle_x = -1.57  # pitch: -π/2 makes Z vertical
    angle_y = 0.0    # yaw: 0 for clean left/right alignment

    print(f"[VIS] Window open. Waiting for UDP data on port {UDP_PORT}...")
    print(f"[VIS] Press V to cycle views: XY / XZ / YZ / 3D")
    print(f"[VIS] Press C to toggle clamping")
    print(f"[VIS] Arrow keys to rotate 3D view")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    trail.clear()
                    trail_3d.clear()
                    packet_count = 0
                elif event.key == pygame.K_v:
                    view_mode = (view_mode + 1) % NUM_VIEWS
                    trail.clear()
                    trail_3d.clear()
                    print(f"[VIS] Switched to {VIEW_NAMES[view_mode]} view")
                elif event.key == pygame.K_z:
                    with position_lock:
                        zero_offset = list(latest_position)
                    trail.clear()
                    trail_3d.clear()
                    print(f"[VIS] Zeroed at X={zero_offset[0]:.3f} Y={zero_offset[1]:.3f} Z={zero_offset[2]:.3f}")
                elif event.key == pygame.K_c:
                    clamp_enabled = not clamp_enabled
                    status = "ON" if clamp_enabled else "OFF"
                    print(f"[VIS] Clamping: {status}")

        # Continuous rotation with held arrow keys
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            angle_y -= 0.03
        if keys[pygame.K_RIGHT]:
            angle_y += 0.03
        if keys[pygame.K_UP]:
            angle_x += 0.03
        if keys[pygame.K_DOWN]:
            angle_x -= 0.03

        # Get current position (with zero offset applied)
        with position_lock:
            pos = [latest_position[i] - zero_offset[i] for i in range(3)]
            t_since = time.time() - last_update_time if last_update_time > 0 else -1
            pkts = packet_count

        # Apply clamping if enabled
        if clamp_enabled:
            pos = clamp_position(pos)

        screen.fill(BG_COLOR)

        if view_mode == VIEW_3D:
            # --- 3D VIEW ---
            z_frac = max(0.0, min(1.0, (pos[2] - WORLD_Z_MIN) / (WORLD_Z_MAX - WORLD_Z_MIN)))
            color = (int(50 + 205 * z_frac), int(200 * (1.0 - z_frac)), int(50 + 205 * (1.0 - z_frac)))

            if last_update_time > 0:
                trail_3d.append((pos[0], pos[1], pos[2], color))
                if len(trail_3d) > max_trail:
                    trail_3d.pop(0)

            draw_3d_view(screen, font, anchor_positions, pos, trail_3d, angle_x, angle_y)

            # HUD
            clamp_status = "[CLAMP]" if clamp_enabled else ""
            hud_lines = [
                f"View: 3D  [V]switch [C]clamp {clamp_status} [Z]zero [R]reset [Arrows]rotate",
                f"Position: X={pos[0]:.3f}  Y={pos[1]:.3f}  Z={pos[2]:.3f} m",
                f"Packets: {pkts}",
            ]

        else:
            # --- 2D VIEWS ---
            h_axis, v_axis, d_axis = VIEW_AXES[view_mode]
            wh = pos[h_axis]
            wv = pos[v_axis]
            wd = pos[d_axis]

            sx, sy = world_to_screen(wh, wv, view_mode)
            color = depth_to_color(wd, view_mode)

            if last_update_time > 0:
                trail.append((sx, sy, color))
                if len(trail) > max_trail:
                    trail.pop(0)

            draw_grid(screen, font, view_mode)
            draw_anchors(screen, font, anchor_positions, view_mode)

            # Draw trail
            for i, (tx, ty, tc) in enumerate(trail):
                alpha = int(50 + 150 * (i / max(len(trail), 1)))
                fade_color = (tc[0] * alpha // 255, tc[1] * alpha // 255, tc[2] * alpha // 255)
                dot_size = max(2, int(SQUARE_SIZE * 0.15))
                pygame.draw.rect(screen, fade_color,
                                 (tx - dot_size // 2, ty - dot_size // 2, dot_size, dot_size))

            # Draw current position square
            half = SQUARE_SIZE // 2
            pygame.draw.rect(screen, color, (sx - half, sy - half, SQUARE_SIZE, SQUARE_SIZE))
            pygame.draw.rect(screen, TEXT_COLOR, (sx - half, sy - half, SQUARE_SIZE, SQUARE_SIZE), 2)

            # Crosshair
            pygame.draw.line(screen, TEXT_COLOR, (sx - half - 5, sy), (sx + half + 5, sy), 1)
            pygame.draw.line(screen, TEXT_COLOR, (sx, sy - half - 5), (sx, sy + half + 5), 1)

            # Depth axis indicator bar
            bar_x = WINDOW_WIDTH - 40
            bar_h = WINDOW_HEIGHT - 100
            bar_y = 50
            pygame.draw.rect(screen, GRID_COLOR, (bar_x, bar_y, 20, bar_h), 1)
            d_min, d_max = WORLD_MINS[d_axis], WORLD_MAXS[d_axis]
            d_frac = max(0.0, min(1.0, (wd - d_min) / (d_max - d_min)))
            d_pixel = int(bar_y + bar_h * (1.0 - d_frac))
            pygame.draw.rect(screen, color, (bar_x + 2, d_pixel - 3, 16, 6))
            d_top_label = font.render(VIEW_D_LABELS[view_mode], True, TEXT_COLOR)
            screen.blit(d_top_label, (bar_x + 4, bar_y - 20))
            d_val_label = font.render(f"{wd:.2f}", True, TEXT_COLOR)
            screen.blit(d_val_label, (bar_x - 15, bar_y + bar_h + 5))

            # HUD
            clamp_status = "[CLAMP]" if clamp_enabled else ""
            hud_lines = [
                f"View: {VIEW_NAMES[view_mode]}  [V]switch [C]clamp {clamp_status} [Z]zero [R]reset",
                f"Position: X={pos[0]:.3f}  Y={pos[1]:.3f}  Z={pos[2]:.3f} m",
                f"Packets: {pkts}",
            ]

        # Common HUD lines
        if t_since >= 0:
            if t_since < 1.0:
                hud_lines.append(f"Last update: {t_since*1000:.0f} ms ago")
            else:
                hud_lines.append(f"Last update: {t_since:.1f} s ago  (stale!)")
        else:
            hud_lines.append("Waiting for data...")

        for i, line in enumerate(hud_lines):
            label = font.render(line, True, TEXT_COLOR)
            screen.blit(label, (10, 10 + i * 22))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()