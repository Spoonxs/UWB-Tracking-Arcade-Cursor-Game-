/*
 * ============================================================
 *  UWB TRILATERATION ANCHOR (SLAVE / PONGER)
 * ============================================================
 *  Board: MakerFab ESP32 UWB DW3000
 *  Role:  Listens for ping frames, checks if addressed to this
 *         anchor (by reading frame payload), responds with pong.
 *
 *  Each anchor must have a UNIQUE ID (0-3) set below.
 *
 *  Fixes included:
 *    - Force-IDLE (writeFastCommand 0x00) before each RX cycle
 *    - Hardware RX timeout via SYS_CFG RXWTOE bit
 *    - Software timeouts on RX and TX while-loops
 * ============================================================
 */

#include "DW3000.h"

// ============================================================
//  CONFIGURATION - CHANGE THIS FOR EACH ANCHOR
// ============================================================

// --- Anchor ID ---
// Set this to 0-5 for each anchor.
// Each anchor in your system MUST have a different ID.
//
//   Ground plane (Z=0):
//     Anchor 0 = (0, 0, 0)       origin
//     Anchor 1 = (1.5, 0, 0)     X axis
//     Anchor 2 = (0, 1.5, 0)     Y axis
//     Anchor 4 = (1.5, 1.5, 0)   XY corner
//   Upper level (Z=1.5):
//     Anchor 3 = (0, 0, 1.5)     Z axis
//     Anchor 5 = (1.5, 1.5, 1.5) opposite corner
//
const int MY_ANCHOR_ID = 4;  // <-- CHANGE FOR EACH ANCHOR (0-5)

// ============================================================
//  INTERNAL STATE
// ============================================================

static int rx_status;
static int tx_status;
int anchor_id;

// ============================================================
//  SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(100);

  anchor_id = MY_ANCHOR_ID;

  Serial.println("\n========================================");
  Serial.printf("  UWB Trilateration ANCHOR %d (Slave)\n", anchor_id);
  Serial.println("========================================\n");

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

  // --- Hardware RX Timeout ---
  // Enable RXWTOE (RX Wait Timeout Enable) in SYS_CFG register
  // This tells the DW3000 to automatically abort RX after a timeout,
  // preventing the chip from getting permanently stuck in RX mode.
  uint32_t sys_cfg = DW3000.read(0x00, 0x10);
  sys_cfg |= (1 << 1);  // Set RXWTOE bit
  DW3000.write(0x00, 0x10, sys_cfg);
  DW3000.write(0x00, 0x20, 50000);  // ~51ms hardware RX timeout

  Serial.printf("[INFO] Anchor %d ready. Waiting for pings...\n\n", anchor_id);
}

// ============================================================
//  MAIN LOOP
// ============================================================

void loop() {
  // Force transceiver to IDLE before starting RX
  // This recovers from any stuck state (known DW3000 hardware bug)
  DW3000.writeFastCommand(0x00);
  delay(1);
  DW3000.clearSystemStatus();

  DW3000.standardRX();

  // Wait for frame with software timeout
  unsigned long rx_start = millis();
  rx_status = 0;
  while (!rx_status && (millis() - rx_start < 500)) {
    rx_status = DW3000.receivedFrameSucc();
    delay(1);
  }

  if (rx_status == 1) {
    // Read the frame payload - the tag puts the target anchor ID
    // as the first byte of the TX frame via setTXFrame(anchor_id).
    // RX_BUFFER_0 is at register 0x12, first byte at offset 0x00.
    int received_id = DW3000.read(0x12, 0x00) & 0xFF;

    if (received_id == anchor_id) {
      // This ping is for us - respond with pong
      DW3000.prepareDelayedTX();
      DW3000.delayedTX();

      DW3000.pullLEDHigh(2);

      // Wait for TX complete with software timeout
      unsigned long tx_start = millis();
      while (!(tx_status = DW3000.sentFrameSucc()) && (millis() - tx_start < 200)) {
        delay(1);
      }

      DW3000.clearSystemStatus();
      DW3000.pullLEDLow(2);

    } else {
      // Not for us - ignore
      DW3000.clearSystemStatus();
    }

  } else {
    // RX timeout or error - just clear and retry
    DW3000.clearSystemStatus();
  }

  delay(5);
}