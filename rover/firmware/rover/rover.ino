// 6WD rocker-bogie rover — Arduino Uno + L298N + HC-05 + HC-SR04.
// Left 3 motors share L298N channel A, right 3 share channel B (skid steering).
// Wiring: see rover/README.md.
#include <SoftwareSerial.h>
#include "rover_logic.h"

// L298N
const uint8_t PIN_ENA = 5;   // PWM, left side
const uint8_t PIN_IN1 = 7;
const uint8_t PIN_IN2 = 8;
const uint8_t PIN_ENB = 6;   // PWM, right side
const uint8_t PIN_IN3 = 9;
const uint8_t PIN_IN4 = 10;
// HM-10 / HC-05 (Uno RX <- BT TX, Uno TX -> divider -> BT RX)
const uint8_t PIN_BT_RX = 2;
const uint8_t PIN_BT_TX = 3;
// HC-SR04
const uint8_t PIN_TRIG = 11;
const uint8_t PIN_ECHO = 12;

// Stop if no command arrives for this long in manual mode (lost link safety).
// Set to 0 if your app only sends a byte on button change instead of repeating it.
const uint32_t CMD_TIMEOUT_MS = 1000;
const uint32_t SONAR_PERIOD_MS = 60;  // HC-SR04 needs >= 60 ms between pings

SoftwareSerial bt(PIN_BT_RX, PIN_BT_TX);
RoverState state = initialState();
AutoState autoState = {AUTO_CRUISE, 0};
uint32_t lastCmdMs = 0;
uint32_t lastPingMs = 0;
int lastDistanceCm = 0;

static void setSide(uint8_t en, uint8_t inA, uint8_t inB, int value) {
  if (value > 0) {
    digitalWrite(inA, HIGH);
    digitalWrite(inB, LOW);
  } else if (value < 0) {
    digitalWrite(inA, LOW);
    digitalWrite(inB, HIGH);
  } else {
    digitalWrite(inA, LOW);
    digitalWrite(inB, LOW);
  }
  analogWrite(en, constrain(abs(value), 0, 255));
}

static void applyDrive(Drive d) {
  setSide(PIN_ENA, PIN_IN1, PIN_IN2, d.left);
  setSide(PIN_ENB, PIN_IN3, PIN_IN4, d.right);
}

// Returns distance in cm, or 0 when no echo within ~3 m.
static int readDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  const unsigned long us = pulseIn(PIN_ECHO, HIGH, 18000UL);
  return (int)(us / 58UL);
}

void setup() {
  const uint8_t outs[] = {PIN_ENA, PIN_IN1, PIN_IN2, PIN_ENB, PIN_IN3, PIN_IN4, PIN_TRIG};
  for (uint8_t i = 0; i < sizeof(outs); i++) pinMode(outs[i], OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  applyDrive(driveFor('S', 0));
  Serial.begin(9600);  // USB serial accepts the same commands, handy for bench tests
  bt.begin(9600);      // HM-10 / HC-05 default baud
}

void loop() {
  const uint32_t now = millis();

  while (bt.available() || Serial.available()) {
    const char c = bt.available() ? (char)bt.read() : (char)Serial.read();
    if (applyCommand(state, c)) {
      lastCmdMs = now;
      if (c == 'X') autoState = {AUTO_CRUISE, now};
    }
  }

  if (now - lastPingMs >= SONAR_PERIOD_MS) {
    lastPingMs = now;
    lastDistanceCm = readDistanceCm();
  }

  if (state.mode == MODE_AUTO) {
    applyDrive(autoStep(autoState, lastDistanceCm, now, state.speed));
    return;
  }

  char cmd = state.lastCmd;
  // Manual safety: never drive forward into something closer than OBSTACLE_CM.
  if ((cmd == 'F' || cmd == 'G' || cmd == 'I') && lastDistanceCm > 0 && lastDistanceCm < OBSTACLE_CM) {
    cmd = 'S';
  }
  if (CMD_TIMEOUT_MS && now - lastCmdMs > CMD_TIMEOUT_MS) cmd = 'S';
  applyDrive(driveFor(cmd, state.speed));
}
