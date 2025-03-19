#include <Wire.h>
#include <SparkFun_FS3000_Arduino_Library.h> // http://librarymanager/All#SparkFun_FS3000

FS3000 fs;

// Define pins for motor control
const int PWM_PIN = 9;   // Speed command (SV) - PWM
const int BRAKE_PIN = 8; // Brake signal
const int DIR_PIN = 7;   // Direction signal
const int EN_PIN = 2;    // Enable signal

float speed_mps;
int speed_pwm = 10;   // Initial PWM value for the fan
float userSpeed = 0;  // Desired speed received from console
float Kp = 20;        // Proportional constant for control
float Kd = 10;        // Derivative constant
float prev_error = 0; // Global for derivative

// We'll store the last time we updated the loop for derivative calculations
unsigned long lastTime = 0;

String incomingCommand = "";

void setup() {
  Serial.begin(115200);
  delay(2000);

  // Setup motor control pins
  pinMode(PWM_PIN, OUTPUT);
  pinMode(BRAKE_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(BRAKE_PIN, HIGH);
  digitalWrite(EN_PIN, LOW);
  analogWrite(PWM_PIN, speed_pwm);

  // FS3000 Sensor Setup
  Serial.println("Starting FS3000 example...");
  Wire.begin();
  if (!fs.begin()) {
    Serial.println("The sensor did not respond. Please check wiring.");
    while (1); // Freeze if sensor not detected
  }
  fs.setRange(AIRFLOW_RANGE_15_MPS);
  Serial.println("Sensor initialized successfully!");
  Serial.println("Sensor is connected properly.");

  // Initialize the time reference for derivative calculations
  lastTime = millis();
}

void loop() {
  // Check for incoming commands
  if (Serial.available() > 0) {
    incomingCommand = Serial.readStringUntil('\n');
    incomingCommand.trim();

    // If command starts with "CS", parse the speed value
    if (incomingCommand.startsWith("CS") && incomingCommand.length() > 2) {
      userSpeed = incomingCommand.substring(2).toInt();
      Serial.print("Set Speed received: ");
      Serial.println(userSpeed);

      // Reset derivative state to avoid a big jump
      prev_error = 0;
    }
  }

  // PD Speed Control (always on in this version)
  // --------------------------------------------
  // 1) Compute dt from millis()
  unsigned long currentTime = millis();
  float dt = (currentTime - lastTime) / 1000.0; // Convert ms to seconds
  lastTime = currentTime;

  // 2) Read the sensor
  speed_mps = fs.readMetersPerSecond();

  // 3) Transmit velocity sensor reading with "AD" prefix
  Serial.print("AD");
  Serial.println(speed_mps, 2);

  // 4) PD control
  float error = userSpeed - speed_mps;
  float dy = error - prev_error;
  float derv = dy / dt;

  int newPWM = int(speed_pwm + (Kp * error) + (Kd * derv));
  speed_pwm = constrain(newPWM, 0, 255);

  // 5) Apply the new PWM immediately
  analogWrite(PWM_PIN, speed_pwm);

  // 6) Send PWM duty cycle with "PWM" prefix
  Serial.print("PWM");
  Serial.println(speed_pwm);

  // 7) Update global prev_error
  prev_error = error;

  // Repeat every ~125 ms (or adjust as needed)
  delay(125);
}
