/* 
  This script receives serial from the main control program.
  When a serial message is received, it increments the sled
  and pulses the LED through red, green, and blue, then awaits
  the next serial pulse.
*/

// Define Pins
#define LO_PIN 12 // LEDs
#define G_PIN 11 
#define R_PIN 10
#define B_PIN 9
#define BZZ_PIN 8
#define IR_PIN A0 // IR Sensor Data Pin
#define MTR_PIN 6

int inByte = 0;
unsigned long curMil = 0;
unsigned long prevMil = 0;

void setup() {
  // Start Serial
  Serial.begin(115200);

  // Assign Pin Modes
  pinMode(LO_PIN, OUTPUT);
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  pinMode(BZZ_PIN, OUTPUT);
  pinMode(MTR_PIN, OUTPUT);

  // Set LED ground pin to low
  digitalWrite(LO_PIN, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    inByte = Serial.read();
    Serial.println(char(inByte));

    if (char(inByte) == 'T') {
      int sensorVal = HIGH;

      // Increment the sled
      prevMil = millis();
      while(curMil - prevMil < 500 || sensorVal == HIGH){
        digitalWrite(BZZ_PIN, HIGH);
        digitalWrite(MTR_PIN, HIGH); 
        sensorVal = digitalRead(IR_PIN);  // Read the value from the IR sensor
        curMil = millis();
      }
      digitalWrite(BZZ_PIN, LOW); 
      digitalWrite(MTR_PIN, LOW); 
      delay(500);

      // Pulse each LED colour in sequence
      digitalWrite(BZZ_PIN, HIGH);  
      analogWrite(R_PIN, 255);
      Serial.println("R");
      delay(100);
      digitalWrite(BZZ_PIN, LOW); 
      delay(500);

      analogWrite(R_PIN, 0);
      digitalWrite(BZZ_PIN, HIGH); 

      analogWrite(G_PIN, 255);
      Serial.println("G");
      delay(100);
      digitalWrite(BZZ_PIN, LOW); 
      delay(500);
      analogWrite(G_PIN, 0);
      digitalWrite(BZZ_PIN, HIGH); 

      analogWrite(B_PIN, 255);
      Serial.println("B");
      delay(100);
      digitalWrite(BZZ_PIN, LOW);  
      delay(500);
      analogWrite(B_PIN, 0);
    }
  }
}
