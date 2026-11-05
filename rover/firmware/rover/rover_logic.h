// Pure logic for the 6WD rocker-bogie rover. No Arduino dependencies,
// so it can be unit-tested on a PC (see firmware/test/test_logic.cpp).
#ifndef ROVER_LOGIC_H
#define ROVER_LOGIC_H

#include <stdint.h>

// Signed motor command per side, -255..255 (positive = forward).
struct Drive {
  int left;
  int right;
};

enum Mode { MODE_MANUAL, MODE_AUTO };

struct RoverState {
  Mode mode;
  uint8_t speed;  // 0..255, set by '0'..'9' and 'q'
  char lastCmd;   // last motion command (F/B/L/R/G/I/H/J/S)
};

inline RoverState initialState() {
  RoverState s = {MODE_MANUAL, 200, 'S'};
  return s;
}

// Motion letters follow the common "Arduino Bluetooth RC Car" app protocol:
// F/B forward/back, L/R pivot, G/I forward-left/right, H/J back-left/right, S stop.
inline Drive driveFor(char cmd, uint8_t speed) {
  const int v = speed;
  const int half = speed / 2;
  switch (cmd) {
    case 'F': return {v, v};
    case 'B': return {-v, -v};
    case 'L': return {-v, v};  // skid-steer pivot in place
    case 'R': return {v, -v};
    case 'G': return {half, v};
    case 'I': return {v, half};
    case 'H': return {-half, -v};
    case 'J': return {-v, -half};
    default: return {0, 0};
  }
}

// Applies one received byte. Returns true if the byte was a recognised command.
// 'X' enters auto (obstacle avoidance) mode, 'x' returns to manual.
// Any motion command also drops back to manual so the driver can always take over.
inline bool applyCommand(RoverState &s, char c) {
  if (c >= '0' && c <= '9') {
    s.speed = (uint8_t)((c - '0') * 255 / 10);
    return true;
  }
  switch (c) {
    case 'q': s.speed = 255; return true;
    case 'X': s.mode = MODE_AUTO; s.lastCmd = 'S'; return true;
    case 'x': s.mode = MODE_MANUAL; s.lastCmd = 'S'; return true;
    case 'F': case 'B': case 'L': case 'R':
    case 'G': case 'I': case 'H': case 'J': case 'S':
      s.mode = MODE_MANUAL;
      s.lastCmd = c;
      return true;
    default:
      return false;  // ignore app extras (lights, horn) and line endings
  }
}

// Obstacle-avoidance state machine, advanced once per loop with the current time.
enum AutoPhase { AUTO_CRUISE, AUTO_BACKUP, AUTO_TURN };

struct AutoState {
  AutoPhase phase;
  uint32_t phaseStart;
};

const int OBSTACLE_CM = 25;      // closer than this = blocked
const uint32_t BACKUP_MS = 400;
const uint32_t TURN_MS = 450;

// distanceCm <= 0 means "no echo" (nothing in range) and is treated as clear.
inline Drive autoStep(AutoState &a, int distanceCm, uint32_t nowMs, uint8_t speed) {
  const bool blocked = distanceCm > 0 && distanceCm < OBSTACLE_CM;
  switch (a.phase) {
    case AUTO_CRUISE:
      if (blocked) {
        a.phase = AUTO_BACKUP;
        a.phaseStart = nowMs;
        return driveFor('B', speed);
      }
      return driveFor('F', speed);
    case AUTO_BACKUP:
      if (nowMs - a.phaseStart >= BACKUP_MS) {
        a.phase = AUTO_TURN;
        a.phaseStart = nowMs;
        return driveFor('R', speed);
      }
      return driveFor('B', speed);
    case AUTO_TURN:
    default:
      if (nowMs - a.phaseStart >= TURN_MS) {
        // Re-check: still blocked -> keep turning another slice, else cruise.
        a.phaseStart = nowMs;
        if (blocked) return driveFor('R', speed);
        a.phase = AUTO_CRUISE;
        return driveFor('F', speed);
      }
      return driveFor('R', speed);
  }
}

#endif
