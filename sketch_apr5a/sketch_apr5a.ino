void setup() {
  Serial.begin(9600);         // Match this with Python baudrate
  Serial.setTimeout(20);      // Wait up to 20ms for data after newline
  Serial.println("Ready");
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');  // Read until newline
    Serial.println("Received:");
    Serial.println(data);  // For now, just echo it to monitor

    // Example: parse first 3 values (x, y, z of wrist)
    int firstComma = data.indexOf(',');
    int secondComma = data.indexOf(',', firstComma + 1);
    int thirdComma = data.indexOf(',', secondComma + 1);

    if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
      int x = data.substring(0, firstComma).toInt();
      int y = data.substring(firstComma + 1, secondComma).toInt();
      float z = data.substring(secondComma + 1, thirdComma).toFloat();

      // You can now use x, y, z for servo control or logic
      Serial.print("Parsed X: "); Serial.println(x);
      Serial.print("Parsed Y: "); Serial.println(y);
      Serial.print("Parsed Z: "); Serial.println(z, 4);
    }
  }
}

