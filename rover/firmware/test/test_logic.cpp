// Host-side tests for rover_logic.h:
//   g++ -std=c++11 -Wall -I../rover test_logic.cpp -o test_logic && ./test_logic
#include <cstdio>
#include "rover_logic.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

static void testSkidSteer() {
  // Pivot turns must spin sides in opposite directions, or the rover cannot turn in place.
  Drive l = driveFor('L', 200);
  CHECK(l.left < 0 && l.right > 0);
  Drive r = driveFor('R', 200);
  CHECK(r.left > 0 && r.right < 0);
  // Arc turns: the inside wheel is slower but same direction.
  Drive g = driveFor('G', 200);
  CHECK(g.left > 0 && g.left < g.right);
  Drive j = driveFor('J', 200);
  CHECK(j.left < 0 && j.right < 0 && j.left < j.right);
  // Unknown command must stop the motors, never keep driving.
  Drive u = driveFor('?', 200);
  CHECK(u.left == 0 && u.right == 0);
}

static void testCommands() {
  RoverState s = initialState();
  CHECK(s.mode == MODE_MANUAL && s.lastCmd == 'S');
  applyCommand(s, '0');
  CHECK(s.speed == 0);
  applyCommand(s, '5');
  CHECK(s.speed == 127);
  applyCommand(s, 'q');
  CHECK(s.speed == 255);
  // Speed changes must not alter the motion command.
  applyCommand(s, 'F');
  applyCommand(s, '3');
  CHECK(s.lastCmd == 'F');
  // Entering auto clears any held motion; a manual motion command takes control back.
  applyCommand(s, 'X');
  CHECK(s.mode == MODE_AUTO && s.lastCmd == 'S');
  applyCommand(s, 'B');
  CHECK(s.mode == MODE_MANUAL && s.lastCmd == 'B');
  // App extras and line endings are ignored and change nothing.
  CHECK(!applyCommand(s, 'W'));
  CHECK(!applyCommand(s, '\n'));
  CHECK(s.lastCmd == 'B');
}

static void testAutoAvoid() {
  AutoState a = {AUTO_CRUISE, 0};
  Drive d = autoStep(a, 100, 0, 200);
  CHECK(a.phase == AUTO_CRUISE && d.left > 0 && d.right > 0);
  // No echo (0) is treated as clear road.
  autoStep(a, 0, 10, 200);
  CHECK(a.phase == AUTO_CRUISE);
  // Obstacle -> reverse immediately.
  d = autoStep(a, 10, 100, 200);
  CHECK(a.phase == AUTO_BACKUP && d.left < 0 && d.right < 0);
  // Keep reversing until BACKUP_MS has elapsed, regardless of distance.
  autoStep(a, 100, 100 + BACKUP_MS - 1, 200);
  CHECK(a.phase == AUTO_BACKUP);
  d = autoStep(a, 100, 100 + BACKUP_MS, 200);
  CHECK(a.phase == AUTO_TURN && d.left > 0 && d.right < 0);
  // After the turn slice, a still-blocked path keeps turning.
  uint32_t t = 100 + BACKUP_MS + TURN_MS;
  d = autoStep(a, 15, t, 200);
  CHECK(a.phase == AUTO_TURN && d.left > 0 && d.right < 0);
  // Once clear after a slice, resume cruising.
  d = autoStep(a, 80, t + TURN_MS, 200);
  CHECK(a.phase == AUTO_CRUISE && d.left > 0 && d.right > 0);
}

int main() {
  testSkidSteer();
  testCommands();
  testAutoAvoid();
  if (failures) { std::printf("%d check(s) failed\n", failures); return 1; }
  std::printf("all rover logic tests passed\n");
  return 0;
}
