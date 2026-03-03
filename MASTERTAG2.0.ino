/*
 * ============================================================
 *  UWB TRILATERATION TAG (MASTER / PINGER)
 * ============================================================
 *  Board: MakerFab ESP32 UWB DW3000
 *  Role:  Sequentially pings 6 anchors, collects distances,
 *         calculates XYZ via least-squares trilateration,
 *         sends over WiFi UDP.
 *
 *  Anchor Layout (6 anchors):
 *    Ground plane (Z=0) - four corners of a 1.5m square:
 *      A0 = (0,    0,    0   )  origin
 *      A1 = (1.5,  0,    0   )  X axis
 *      A2 = (0,    1.5,  0   )  Y axis
 *      A4 = (1.5,  1.5,  0   )  XY diagonal corner
 *    Upper level (Z=1.5) - two opposite corners:
 *      A3 = (0,    0,    1.5 )  Z axis
 *      A5 = (1.5,  1.5,  1.5 )  opposite corner
 *
 *  True distances from origin (for calibration):
 *      A0 = 0 m
 *      A1 = 1.5 m
 *      A2 = 1.5 m
 *      A3 = 1.5 m
 *      A4 = sqrt(1.5^2 + 1.5^2 + 1.5^2) = ~2.598 m
 *      A5 = sqrt(1.5^2 + 1.5^2)         = ~2.121 m
 *
 *  Trilateration: Least-squares (A^T*A)x = A^T*b
 *    6 anchors → 5 linearized equations → 3 unknowns
 *    Overdetermined system minimizes overall error
 *
 *  Flow:
 *    1. Connect to WiFi
 *    2. Auto-calibrate: tag at origin, measure per-anchor
 *       antenna delays using known true distances
 *    3. Loop: Ping A0-A5, least-squares XYZ, send via UDP
 * ============================================================
 */

#include "DW3000.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <math.h>

// ============================================================
//  CONFIGURATION - CHANGE THESE VALUES
// ============================================================

// --- WiFi ---
const char* WIFI_SSID      = "PrincipledInterfaces";       // <-- CHANGE
const char* WIFI_PASSWORD   = "Daley310!";    // <-- CHANGE
const char* UDP_TARGET_IP   = "192.168.0.198";         // <-- PC IP running visualizer
const int   UDP_TARGET_PORT = 9000;                    // <-- UDP port

// --- Number of active anchors ---
const int NUM_ANCHORS = 6;

// --- Calibration ---
const bool CALIBRATION_ON_STARTUP = true;
const int  CALIBRATION_SAMPLES    = 30;
const int  CALIBRATION_WARMUP     = 5;

// --- Anchor edge length (meters) ---
// All anchors are placed on corners of a cube with this edge length.
// The true distance from origin to each anchor is calculated
// automatically using the Pythagorean theorem.
const float EDGE_LENGTH = 3.3528;

// --- Anchor Positions (meters) ---
// Ground plane: 4 corners of a square (A0, A1, A2, A4)
// Upper level: 2 opposite corners (A3 above A0, A5 above A4)
// These are the KNOWN positions. Calibration does NOT change them.
float ANCHOR_X[6] = { 0.0,         EDGE_LENGTH, 0.0,         0.0,         EDGE_LENGTH, EDGE_LENGTH };
float ANCHOR_Y[6] = { 0.0,         0.0,         EDGE_LENGTH, 0.0,         EDGE_LENGTH, EDGE_LENGTH };
float ANCHOR_Z[6] = { 0.0,         0.0,         0.0,         EDGE_LENGTH, 0.0,         EDGE_LENGTH };

// --- True distances from origin (auto-calculated) ---
// Used during calibration to determine per-anchor antenna delay.
// A0 = 0, A1 = 1.5, A2 = 1.5, A3 = ~2.121, A4 = 1.5, A5 = ~2.598
float TRUE_DIST[6];

// --- Per-Anchor Antenna Delay Offsets (meters) ---
float distance_offset[6] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };

// --- Filtering ---
const float EMA_ALPHA = 0.5;  // 0.0-1.0; lower = smoother, higher = responsive

// --- Timing ---
const int PING_TIMEOUT_MS = 30;
const int INTER_ANCHOR_MS = 10;
const int CYCLE_DELAY_MS  = 20;

// ============================================================
//  INTERNAL STATE
// ============================================================

static int rx_status;
static int tx_status;

float raw_distances[6]      = {0, 0, 0, 0, 0, 0};
float filtered_distances[6] = {0, 0, 0, 0, 0, 0};
float position[3]           = {0, 0, 0};
float filtered_position[3]  = {0, 0, 0};
bool  anchor_valid[6]       = {false, false, false, false, false, false};
bool  anchor_ever_seen[6]   = {false, false, false, false, false, false};

WiFiUDP udp;

// ============================================================
//  SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n========================================");
  Serial.println("  UWB Trilateration TAG (Master)");
  Serial.println("  6-Anchor Least-Squares Mode");
  Serial.println("========================================");
  Serial.println("  A0 = (0,    0,    0   )  origin");
  Serial.println("  A1 = (1.5,  0,    0   )  X axis");
  Serial.println("  A2 = (0,    1.5,  0   )  Y axis");
  Serial.println("  A3 = (0,    0,    1.5 )  Z axis");
  Serial.println("  A4 = (1.5,  1.5,  0   )  XY corner");
  Serial.println("  A5 = (1.5,  1.5,  1.5 )  opposite corner");
  Serial.println("========================================\n");

  // --- Calculate true distances from origin ---
  // Each anchor's distance = sqrt(x^2 + y^2 + z^2)
  Serial.println("[INFO] True distances from origin:");
  for (int i = 0; i < NUM_ANCHORS; i++) {
    TRUE_DIST[i] = sqrt(ANCHOR_X[i]*ANCHOR_X[i] +
                        ANCHOR_Y[i]*ANCHOR_Y[i] +
                        ANCHOR_Z[i]*ANCHOR_Z[i]);
    Serial.printf("  A%d at (%.1f, %.1f, %.1f) = %.4f m\n",
                  i, ANCHOR_X[i], ANCHOR_Y[i], ANCHOR_Z[i], TRUE_DIST[i]);
  }

  // --- WiFi ---
  Serial.print("\n[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempts < 40) {
    delay(500);
    Serial.print(".");
    wifi_attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\n[WiFi] Connected! IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Connection FAILED - continuing without WiFi");
  }

  // --- DW3000 Init ---
  DW3000.begin();
  DW3000.hardReset();
  delay(200);

  if (!DW3000.checkSPI()) {
    Serial.println("[ERROR] SPI connection to DW3000 failed!");
    while (1) { delay(1000); }
  }

  while (!DW3000.checkForIDLE()) {
    Serial.println("[ERROR] IDLE1 FAILED");
    delay(1000);
  }

  DW3000.softReset();
  delay(200);

  if (!DW3000.checkForIDLE()) {
    Serial.println("[ERROR] IDLE2 FAILED");
    while (1) { delay(1000); }
  }

  DW3000.init();
  DW3000.setupGPIO();
  DW3000.configureAsTX();
  DW3000.clearSystemStatus();

  Serial.println("[DW3000] Initialized successfully.");

  // --- Auto-Calibration ---
  if (CALIBRATION_ON_STARTUP) {
    runAutoCalibration();
  }

  // --- Print final config ---
  Serial.println("\n[INFO] Final anchor positions (meters):");
  for (int i = 0; i < NUM_ANCHORS; i++) {
    Serial.printf("  A%d: (%.3f, %.3f, %.3f)  true_dist=%.4f m  offset=%.4f m\n",
                  i, ANCHOR_X[i], ANCHOR_Y[i], ANCHOR_Z[i],
                  TRUE_DIST[i], distance_offset[i]);
  }
  Serial.printf("\n[INFO] Starting trilateration. Pinging %d anchors.\n\n", NUM_ANCHORS);
}

// ============================================================
//  MAIN LOOP
// ============================================================

void loop() {
  int valid_count = 0;

  for (int anchor_id = 0; anchor_id < NUM_ANCHORS; anchor_id++) {
    float dist = pingAnchor(anchor_id);
    if (dist > 0) {
      // Apply per-anchor antenna delay offset
      dist = dist - distance_offset[anchor_id];
      if (dist < 0) dist = 0.01;

      raw_distances[anchor_id] = dist;

      if (filtered_distances[anchor_id] == 0) {
        filtered_distances[anchor_id] = dist;
      } else {
        filtered_distances[anchor_id] = EMA_ALPHA * dist + (1.0 - EMA_ALPHA) * filtered_distances[anchor_id];
      }

      anchor_valid[anchor_id] = true;
      anchor_ever_seen[anchor_id] = true;
      valid_count++;
    } else {
      anchor_valid[anchor_id] = false;
    }

    delay(INTER_ANCHOR_MS);
  }

  // --- Trilaterate ---
  // Need at least 4 anchors (reference + 3 equations for 3 unknowns)
  if (valid_count >= 4) {
    float trilat_distances[6];
    bool using_cached = false;

    for (int i = 0; i < NUM_ANCHORS; i++) {
      trilat_distances[i] = filtered_distances[i];

      if (!anchor_valid[i]) {
        if (anchor_ever_seen[i]) {
          using_cached = true;
        } else {
          // Never seen this anchor — skip it in trilateration
          trilat_distances[i] = -1;
        }
      }
    }

    bool success = trilaterateLeastSquares(trilat_distances, position);

    if (success) {
      for (int i = 0; i < 3; i++) {
        filtered_position[i] = EMA_ALPHA * position[i] + (1.0 - EMA_ALPHA) * filtered_position[i];
      }

      Serial.printf("XYZ: %.3f, %.3f, %.3f  |  %d/%d anchors%s\n",
                    filtered_position[0], filtered_position[1], filtered_position[2],
                    valid_count, NUM_ANCHORS,
                    using_cached ? "  [CACHED]" : "");

      sendPositionUDP(filtered_position[0], filtered_position[1], filtered_position[2]);
    } else {
      Serial.println("[WARN] Trilateration failed");
    }

  } else {
    Serial.printf("[WARN] Only %d/%d anchors responded (need at least 4)\n",
                  valid_count, NUM_ANCHORS);
  }

  delay(CYCLE_DELAY_MS);
}

// ============================================================
//  PING AN ANCHOR AND GET DISTANCE
// ============================================================

float pingAnchor(int anchor_id) {
  DW3000.writeFastCommand(0x00);  // Force transceiver to IDLE
  delay(1);
  DW3000.clearSystemStatus();

  DW3000.setTXFrame(anchor_id);
  DW3000.setFrameLength(1);

  DW3000.TXInstantRX();

  unsigned long start = millis();
  while (!(tx_status = DW3000.sentFrameSucc())) {
    if (millis() - start > PING_TIMEOUT_MS) {
      DW3000.writeFastCommand(0x00);
      DW3000.clearSystemStatus();
      return -1;
    }
  }
  DW3000.clearSystemStatus();

  start = millis();
  while (!(rx_status = DW3000.receivedFrameSucc())) {
    if (millis() - start > PING_TIMEOUT_MS) {
      DW3000.writeFastCommand(0x00);
      DW3000.clearSystemStatus();
      return -1;
    }
  }

  if (rx_status == 1) {
    double dist_cm = DW3000.calculateTXRXdiff();
    if (dist_cm < 0) {
      DW3000.clearSystemStatus();
      return -1;
    }
    double dist_m = dist_cm / 100.0;
    DW3000.clearSystemStatus();
    return dist_m;
  } else {
    DW3000.writeFastCommand(0x00);
    DW3000.clearSystemStatus();
    return -1;
  }
}

// ============================================================
//  AUTO-CALIBRATION ROUTINE
// ============================================================
//
//  Place TAG at A0 (origin 0,0,0). All anchors at their known
//  positions. Each anchor has a known true distance from origin
//  calculated from its coordinates via Pythagorean theorem:
//
//    A0 = 0m,  A1 = 1.5m,  A2 = 1.5m,  A3 = 1.5m
//    A4 = sqrt(1.5^2 + 1.5^2)         = ~2.121m
//    A5 = sqrt(1.5^2 + 1.5^2 + 1.5^2) = ~2.598m
//
//  Per-anchor antenna delay:
//    offset[i] = measured[i] - TRUE_DIST[i]

void runAutoCalibration() {
  Serial.println("\n========================================");
  Serial.println("  AUTO-CALIBRATION (6 Anchors)");
  Serial.println("========================================");
  Serial.println("  Anchor positions must be set up:");
  Serial.printf("  A0 (0,0,0)          true dist = %.3f m\n", TRUE_DIST[0]);
  Serial.printf("  A1 (%.1f,0,0)        true dist = %.3f m\n", EDGE_LENGTH, TRUE_DIST[1]);
  Serial.printf("  A2 (0,%.1f,0)        true dist = %.3f m\n", EDGE_LENGTH, TRUE_DIST[2]);
  Serial.printf("  A3 (0,0,%.1f)        true dist = %.3f m\n", EDGE_LENGTH, TRUE_DIST[3]);
  Serial.printf("  A4 (%.1f,%.1f,0)     true dist = %.3f m\n", EDGE_LENGTH, EDGE_LENGTH, TRUE_DIST[4]);
  Serial.printf("  A5 (%.1f,%.1f,%.1f)  true dist = %.3f m\n", EDGE_LENGTH, EDGE_LENGTH, EDGE_LENGTH, TRUE_DIST[5]);
  Serial.println("\n  Place TAG at A0 (origin 0,0,0).");
  Serial.println("  Hold still for calibration...");
  Serial.println("  Starting in 5 seconds...\n");
  delay(5000);

  float sum_dist[6] = {0};
  int   count[6]    = {0};

  // Warmup
  Serial.println("[CAL] Warmup phase...");
  for (int s = 0; s < CALIBRATION_WARMUP; s++) {
    for (int a = 0; a < NUM_ANCHORS; a++) {
      pingAnchor(a);
      delay(INTER_ANCHOR_MS);
    }
    delay(50);
  }

  // Collect samples
  Serial.println("[CAL] Collecting samples...");
  for (int s = 0; s < CALIBRATION_SAMPLES; s++) {
    Serial.printf("  Sample %d/%d:", s + 1, CALIBRATION_SAMPLES);
    for (int a = 0; a < NUM_ANCHORS; a++) {
      float d = pingAnchor(a);
      if (d > 0) {
        sum_dist[a] += d;
        count[a]++;
        Serial.printf("  A%d=%.2f", a, d);
      } else {
        Serial.printf("  A%d=FAIL", a);
      }
      delay(INTER_ANCHOR_MS);
    }
    Serial.println();
    delay(50);
  }

  // Calculate averages
  float avg_dist[6] = {0};
  bool  cal_ok = true;

  Serial.println("\n--- Raw Averages ---");
  for (int a = 0; a < NUM_ANCHORS; a++) {
    if (count[a] > 0) {
      avg_dist[a] = sum_dist[a] / count[a];
      Serial.printf("  A%d: avg=%.4f m  (%d/%d samples)\n",
                    a, avg_dist[a], count[a], CALIBRATION_SAMPLES);
    } else {
      Serial.printf("  A%d: NO RESPONSE! Calibration failed for this anchor.\n", a);
      cal_ok = false;
    }
  }

  if (!cal_ok) {
    Serial.println("\n[ERROR] Calibration incomplete! Using zero offsets.");
    Serial.println("========================================\n");
    return;
  }

  // --- Calculate per-anchor antenna delay offsets ---
  //
  // offset[i] = measured_distance[i] - true_distance[i]
  //
  // A0 is at origin → true distance = 0, so offset = entire reading
  // A1 is at 1.5m → offset = measured - 1.5
  // A3 is at ~2.121m → offset = measured - 2.121
  // A5 is at ~2.598m → offset = measured - 2.598

  Serial.println("\n--- Per-Anchor Antenna Delay Offsets ---");
  for (int a = 0; a < NUM_ANCHORS; a++) {
    distance_offset[a] = avg_dist[a] - TRUE_DIST[a];
    Serial.printf("  A%d: measured %.4f m, true %.4f m  ->  offset = %+.4f m\n",
                  a, avg_dist[a], TRUE_DIST[a], distance_offset[a]);
  }

  // Print hardcoded values for backup
  Serial.print("\n  Hardcoded offsets: { ");
  for (int a = 0; a < NUM_ANCHORS; a++) {
    Serial.printf("%.4f", distance_offset[a]);
    if (a < NUM_ANCHORS - 1) Serial.print(", ");
  }
  Serial.println(" };");

  Serial.println("\n[CAL] Calibration complete! Switching to trilateration mode.");
  Serial.println("========================================\n");
}

// ============================================================
//  LEAST-SQUARES TRILATERATION (6-anchor)
// ============================================================
//
//  Each anchor gives a sphere equation:
//    (x - xi)^2 + (y - yi)^2 + (z - zi)^2 = di^2
//
//  Expanding and subtracting the reference anchor (A0):
//    2(x0-xi)*x + 2(y0-yi)*y + 2(z0-zi)*z = di^2 - d0^2 - ri^2 + r0^2
//
//  where ri^2 = xi^2 + yi^2 + zi^2
//
//  This gives N-1 linear equations for 3 unknowns (x, y, z).
//  With 6 anchors we get 5 equations → overdetermined system.
//
//  Least-squares solution: (A^T * A) * p = A^T * b
//  where A is (N-1)x3, b is (N-1)x1, p is [x, y, z]
//
//  We solve the 3x3 normal equations via Gaussian elimination.

bool trilaterateLeastSquares(float distances[6], float result[3]) {
  // Find reference anchor (first one with valid distance)
  int ref = -1;
  for (int i = 0; i < NUM_ANCHORS; i++) {
    if (distances[i] > 0) {
      ref = i;
      break;
    }
  }
  if (ref < 0) return false;

  float x0 = ANCHOR_X[ref], y0 = ANCHOR_Y[ref], z0 = ANCHOR_Z[ref];
  float d0_sq = distances[ref] * distances[ref];
  float r0_sq = x0*x0 + y0*y0 + z0*z0;

  // Build the overdetermined system A*p = b
  // Maximum 5 rows (6 anchors - 1 reference)
  float A[5][3];
  float b[5];
  int n_eq = 0;

  for (int i = 0; i < NUM_ANCHORS; i++) {
    if (i == ref) continue;
    if (distances[i] <= 0) continue;  // Skip missing anchors

    float xi = ANCHOR_X[i], yi = ANCHOR_Y[i], zi = ANCHOR_Z[i];
    float di_sq = distances[i] * distances[i];
    float ri_sq = xi*xi + yi*yi + zi*zi;

    A[n_eq][0] = 2.0 * (x0 - xi);
    A[n_eq][1] = 2.0 * (y0 - yi);
    A[n_eq][2] = 2.0 * (z0 - zi);
    b[n_eq]    = di_sq - d0_sq - ri_sq + r0_sq;

    n_eq++;
  }

  // Need at least 3 equations for 3 unknowns
  if (n_eq < 3) {
    Serial.printf("[WARN] Only %d equations, need at least 3\n", n_eq);
    return false;
  }

  // Compute A^T * A (3x3) and A^T * b (3x1)
  float ATA[3][3] = {{0}};
  float ATb[3]    = {0};

  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      for (int k = 0; k < n_eq; k++) {
        ATA[i][j] += A[k][i] * A[k][j];
      }
    }
    for (int k = 0; k < n_eq; k++) {
      ATb[i] += A[k][i] * b[k];
    }
  }

  // Solve 3x3 system ATA * p = ATb via Gaussian elimination with pivoting
  float M[3][4]; // Augmented matrix [ATA | ATb]
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
      M[i][j] = ATA[i][j];
    }
    M[i][3] = ATb[i];
  }

  for (int col = 0; col < 3; col++) {
    // Partial pivoting
    int max_row = col;
    float max_val = fabs(M[col][col]);
    for (int row = col + 1; row < 3; row++) {
      if (fabs(M[row][col]) > max_val) {
        max_val = fabs(M[row][col]);
        max_row = row;
      }
    }

    if (max_val < 1e-6) {
      Serial.println("[ERROR] Least-squares matrix is singular!");
      return false;
    }

    // Swap rows
    if (max_row != col) {
      for (int j = 0; j < 4; j++) {
        float tmp = M[col][j];
        M[col][j] = M[max_row][j];
        M[max_row][j] = tmp;
      }
    }

    // Eliminate below
    for (int row = col + 1; row < 3; row++) {
      float factor = M[row][col] / M[col][col];
      for (int j = col; j < 4; j++) {
        M[row][j] -= factor * M[col][j];
      }
    }
  }

  // Back substitution
  result[2] = M[2][3] / M[2][2];
  result[1] = (M[1][3] - M[1][2] * result[2]) / M[1][1];
  result[0] = (M[0][3] - M[0][1] * result[1] - M[0][2] * result[2]) / M[0][0];

  // Sanity check: compute residuals
  float max_residual = 0;
  for (int i = 0; i < NUM_ANCHORS; i++) {
    if (distances[i] <= 0) continue;
    float dx = result[0] - ANCHOR_X[i];
    float dy = result[1] - ANCHOR_Y[i];
    float dz = result[2] - ANCHOR_Z[i];
    float computed_dist = sqrt(dx*dx + dy*dy + dz*dz);
    float residual = fabs(computed_dist - distances[i]);
    if (residual > max_residual) max_residual = residual;
  }

  if (max_residual > 1.0) {
    Serial.printf("[WARN] Large residual: %.3f m\n", max_residual);
  }

  return true;
}

// ============================================================
//  SEND POSITION VIA UDP
// ============================================================

void sendPositionUDP(float x, float y, float z) {
  if (WiFi.status() != WL_CONNECTED) return;

  char buf[64];
  snprintf(buf, sizeof(buf), "%.4f,%.4f,%.4f", x, y, z);

  udp.beginPacket(UDP_TARGET_IP, UDP_TARGET_PORT);
  udp.print(buf);
  udp.endPacket();
}