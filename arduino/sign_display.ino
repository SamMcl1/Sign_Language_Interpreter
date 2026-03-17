// Sign Language Interpreter - Arduino Display Controller
//
// 7-segment display (F5101BH, common anode):
//   Segment pins: A=7, B=8, C=5, D=4, E=9, F=2, G=3
//   Common (VCC): column 7 on breadboard -> 5V
//
// LEDs:
//   Green  = Pin 11 (recording / ready)
//   Yellow = Pin 12 (displaying word)
//   Red    = Pin 10 (not recording)
//
// Serial protocol (9600 baud):
//   Receives "START", "STOP", or a sign word from Raspberry Pi

const int SEG_A=7, SEG_B=8, SEG_C=5, SEG_D=4, SEG_E=9, SEG_F=2, SEG_G=3;
const int GREEN_LED=11, YELLOW_LED=12, RED_LED=10;

const bool GLYPHS[14][7] = {
  {1,0,0,1,1,1,1}, // 0  = 1
  {1,0,0,1,0,0,0}, // 1  = H
  {0,1,1,0,0,0,0}, // 2  = E
  {1,1,1,0,0,0,1}, // 3  = L
  {0,0,0,0,0,0,1}, // 4  = O
  {1,0,0,0,1,0,0}, // 5  = Y
  {0,1,0,0,1,0,0}, // 6  = S
  {1,1,0,1,0,1,0}, // 7  = n
  {0,0,1,1,0,0,0}, // 8  = P
  {1,1,1,0,0,0,0}, // 9  = t
  {0,0,0,1,0,0,0}, // 10 = A
  {0,1,1,0,0,1,0}, // 11 = C
  {1,0,0,0,0,0,1}, // 12 = U
  {1,0,0,0,0,1,1}, // 13 = i
};

int PINS[7] = {SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G};

void showGlyph(int idx) {
  for (int i = 0; i < 7; i++) digitalWrite(PINS[i], GLYPHS[idx][i]);
}

void blankDisplay() {
  for (int i = 0; i < 7; i++) digitalWrite(PINS[i], HIGH);
}

void setLED(bool red, bool yellow, bool green) {
  digitalWrite(RED_LED,    red    ? HIGH : LOW);
  digitalWrite(YELLOW_LED, yellow ? HIGH : LOW);
  digitalWrite(GREEN_LED,  green  ? HIGH : LOW);
}

void displayWord(int* seq, int len) {
  setLED(false, true, false);
  for (int i = 0; i < len; i++) {
    showGlyph(seq[i]);
    delay(500);
  }
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

    int seqHello[5] = {1,2,3,3,4};
    int seqYes[3]   = {5,2,6};
    int seqNo[2]    = {7,4};
    int seqPeace[4] = {8,2,10,11};
    int seqILY[3]   = {13,3,12};
    int seqOne[1]   = {0};
    int seqStop[4]  = {6,9,4,8};

    if      (received == "hello")      displayWord(seqHello, 5);
    else if (received == "yes")        displayWord(seqYes,   3);
    else if (received == "no")         displayWord(seqNo,    2);
    else if (received == "peace")      displayWord(seqPeace, 4);
    else if (received == "i love you") displayWord(seqILY,   3);
    else if (received == "one")        displayWord(seqOne,   1);
    else if (received == "fist")       displayWord(seqStop,  4);
    else if (received == "stop")       displayWord(seqStop,  4);
  }
}
