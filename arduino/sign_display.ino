// Sign Language Interpreter - Arduino Display Controller
//
// 7-segment display (F5101BH, common anode):
//   Segment pins: A=7, B=8, C=5, D=4, E=9, F=2, G=3
//   Common (VCC): column 7 on breadboard -> 5V
//
// LEDs:
//   Green  = Pin 11 (recording / ready)
//   Yellow = Pin 12 (displaying letter)
//   Red    = Pin 10 (not recording)
//
// Serial protocol (9600 baud):
//   Receives "START", "STOP", "del", "space", or a single letter A-Z

const int SEG_A=7, SEG_B=8, SEG_C=5, SEG_D=4, SEG_E=9, SEG_F=2, SEG_G=3;
const int GREEN_LED=11, YELLOW_LED=12, RED_LED=10;

// Glyph table for A-Z: 0=segment ON, 1=segment OFF (common anode)
// Segment order: [A, B, C, D, E, F, G]
// Letters with no good 7-seg representation are left blank (all 1s)
const bool LETTER_GLYPHS[26][7] = {
  {0,0,0,1,0,0,0}, // A
  {1,1,0,0,0,0,0}, // b (lowercase)
  {0,1,1,0,0,0,1}, // C
  {1,0,0,0,0,1,0}, // d (lowercase)
  {0,1,1,0,0,0,0}, // E
  {0,1,1,1,0,0,0}, // F
  {0,0,0,0,1,0,0}, // G (like 9)
  {1,0,0,1,0,0,0}, // H
  {1,0,0,1,1,1,1}, // I (right side, like 1)
  {1,0,0,0,0,1,1}, // J
  {1,1,1,1,1,1,1}, // K - blank (no good representation)
  {1,1,1,0,0,0,1}, // L
  {1,1,1,1,1,1,1}, // M - blank (no good representation)
  {1,1,0,1,0,0,0}, // n (lowercase)
  {0,0,0,0,0,0,1}, // O
  {0,0,1,1,0,0,0}, // P
  {1,1,1,1,1,1,1}, // Q - blank (no good representation)
  {1,1,1,1,0,0,0}, // r (lowercase)
  {0,1,0,0,1,0,0}, // S
  {1,1,1,0,0,0,0}, // t (lowercase)
  {1,0,0,0,0,0,1}, // U
  {1,1,1,1,1,1,1}, // V - blank (no good representation)
  {1,1,1,1,1,1,1}, // W - blank (no good representation)
  {1,1,1,1,1,1,1}, // X - blank (no good representation)
  {1,0,0,0,1,0,0}, // Y
  {0,0,1,0,0,1,0}, // Z
};

int PINS[7] = {SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G};

void showLetterGlyph(const bool* glyph) {
  for (int i = 0; i < 7; i++) digitalWrite(PINS[i], glyph[i] ? HIGH : LOW);
}

void blankDisplay() {
  for (int i = 0; i < 7; i++) digitalWrite(PINS[i], HIGH);
}

void setLED(bool red, bool yellow, bool green) {
  digitalWrite(RED_LED,    red    ? HIGH : LOW);
  digitalWrite(YELLOW_LED, yellow ? HIGH : LOW);
  digitalWrite(GREEN_LED,  green  ? HIGH : LOW);
}

void displayLetter(char c) {
  c = toupper(c);
  if (c < 'A' || c > 'Z') return;
  setLED(false, true, false);
  showLetterGlyph(LETTER_GLYPHS[c - 'A']);
  delay(800);
  blankDisplay();
  setLED(false, false, true);
}

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 7; i++) {
    pinMode(PINS[i], OUTPUT);
    digitalWrite(PINS[i], HIGH);
  }
  pinMode(RED_LED,    OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED,  OUTPUT);
  setLED(true, false, false);
}

void loop() {
  if (Serial.available()) {
    String received = Serial.readStringUntil('\n');
    received.trim();

    if (received == "START") { setLED(false, false, true); return; }
    if (received == "STOP")  { setLED(true, false, false); blankDisplay(); return; }
    if (received == "del" || received == "space" || received == "nothing") return;

    if (received.length() == 1) {
      displayLetter(received.charAt(0));
    }
  }
}
