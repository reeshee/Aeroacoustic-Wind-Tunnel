#include <Wire.h>
#include <SparkFun_FS3000_Arduino_Library.h> // http://librarymanager/All#SparkFun_FS3000

FS3000 fs;

// Define pins for motor control
const int PWM_PIN = 9;  // Speed command (SV) - PWM
const int BRAKE_PIN = 8; // Brake signal (BRK)
const int DIR_PIN = 7;   // Direction signal (F/R)
const int EN_PIN = 2;    // Enable signal (EN)

const int AVERAGE_COUNT = 512; // Number of averaging points for integral control
const int GAIN_POINTS = 6;  // Number of data points for the gain lookup table, should be one per meter per second

const float pGains[GAIN_POINTS] = {0.03, 0.04, 0.035, 0.04, 0.04, 0.06};             // Proportional constant for control    
const float dGains[GAIN_POINTS] = {0.01, 0.01, 0.01, 0.01, 0.02, 0.01};             // Derivatice constant for control
const float iGains[GAIN_POINTS] = {0.1, 0.15, 0.15, 0.15, 0.2, 0.2};             // Integral constant for control

float Kp = 0;
float Kd = 0;
float Ki = 0;

float speed_mps;
int speed_pwm = 0;      // Initial PWM value for the fan
float userSpeed = 0;       // Desired speed received from console
float prev_error[AVERAGE_COUNT];
bool speedControl = true;

unsigned long lastTime = 0;
unsigned long currentTime = 0;
float dt = 0;

String incomingCommand = "";

void setup() 
{
  Serial.begin(115200);  // Use 115200 baud rate to match your setup
  delay(2000);

  // Setup motor control pins
  pinMode(PWM_PIN, OUTPUT);
  pinMode(BRAKE_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(BRAKE_PIN, LOW);
  digitalWrite(EN_PIN, HIGH);
  
  analogWrite(PWM_PIN, speed_pwm);

  // FS3000 Sensor Setup
  Serial.println("Starting FS3000 example...");
  Wire.begin();
  if (!fs.begin()) 
  {
    Serial.println("The sensor did not respond. Please check wiring.");
    while (1); // Freeze if sensor not detected
  }
  Serial.println("Sensor initialized successfully!");
  
  // If using the FS3000-1015, set range to AIRFLOW_RANGE_15_MPS
  fs.setRange(AIRFLOW_RANGE_15_MPS);
  Serial.println("Sensor is connected properly.");

  for (int i = 0; i < AVERAGE_COUNT; i++)
  {
    prev_error[i] = 0;
  }

  Kp = linInterpolate(pGains, userSpeed);
  Kd = linInterpolate(dGains, userSpeed);
  Ki = linInterpolate(iGains, userSpeed);
}

void loop() 
{

  lastTime = currentTime;
  currentTime = millis();
  dt = (float)(currentTime - lastTime)/1000;

  // Check for incoming commands from the console
  if (Serial.available() > 0) 
  {
    incomingCommand = Serial.readStringUntil('\n');
    incomingCommand.trim(); // Remove extra whitespace/newlines

    // If command starts with "CS", parse the speed value
    if (incomingCommand.startsWith("CS") && incomingCommand.length() > 2) 
    {
      userSpeed = incomingCommand.substring(2).toFloat();
      Serial.print("Set Speed received: ");
      Serial.println(userSpeed);
      speedControl = true;

      if(userSpeed == 0)
      {
        digitalWrite(EN_PIN, HIGH);
        delay(1000);
        digitalWrite(BRAKE_PIN, LOW);
      }
      else
      {
        digitalWrite(EN_PIN, LOW);
        digitalWrite(BRAKE_PIN, HIGH);
      }
      
      Kp = linInterpolate(pGains, userSpeed);
      Kd = linInterpolate(dGains, userSpeed);
      Ki = linInterpolate(iGains, userSpeed);

    } // If command starts with "MP", parse the PWM value
    else if (incomingCommand.startsWith("MP") && incomingCommand.length() > 2) 
    {
      speed_pwm = incomingCommand.substring(2).toInt();
      Serial.print("Set PWM received: ");
      Serial.println(speed_pwm);
      speedControl = false;

      if(speed_pwm == 0)
      {
        digitalWrite(EN_PIN, HIGH);
        delay(1000);
        digitalWrite(BRAKE_PIN, LOW);
      }
      else
      {
        digitalWrite(EN_PIN, LOW);
        digitalWrite(BRAKE_PIN, HIGH);
      }
    } 
    else 
    {
      Serial.print("Invalid command received: ");
      Serial.println(incomingCommand);
    }
  }
  
  if (speedControl) 
  {
    // Read sensor value from FS3000
    speed_mps = fs.readMetersPerSecond();

    // Transmit velocity sensor reading with "AD" prefix
    Serial.print("AD");
    Serial.println(speed_mps, 2);

    // Transmit PWM duty cycle
    Serial.print("PWM");
    Serial.println(speed_pwm);

    // Proportional
    float proportionalError = userSpeed - speed_mps;
    float p = proportionalError * Kp;
    
    // Derivative
    float dy = proportionalError - prev_error[0];
    float derivativeError = dy/dt;
    float d = derivativeError * Kd;

    // Integral
    errorShift(prev_error, proportionalError);
    float integralError = average(prev_error);
    float i = integralError * Ki;

    // PD Controller
    float control = 255 * (p + i + d) / speed_mps;

    int controlInt = (int)(control);
    float controlDecimal = control - controlInt;

    int newPWM = 0;

    if(controlDecimal >= 0.5)
      newPWM = int(speed_pwm + control) + 1;
    else
      newPWM = int(speed_pwm + control);

    //int newPWM = int(speed_pwm + control);
    
    speed_pwm = constrain(newPWM, 0, 255);    // Constrain the PWM boundaries

    analogWrite(PWM_PIN, speed_pwm);

  } 
  else if (!speedControl) 
  {
    // Read sensor value from FS3000
    speed_mps = fs.readMetersPerSecond();

    // Transmit velocity sensor reading with "AD" prefix
    Serial.print("AD");
    Serial.println(speed_mps, 2);

    // Transmit PWM duty cycle
    Serial.print("PWM");
    Serial.println(speed_pwm);

    // PWM controlled
    analogWrite(PWM_PIN, speed_pwm);
  }

  delay(50);
  
}

float average(float values[AVERAGE_COUNT])
{
  int count = 0;

  for(int i = 0; i < AVERAGE_COUNT; i++)
  {
    count = count + values[i];
  }

  return count/AVERAGE_COUNT;
}

void errorShift(float values[AVERAGE_COUNT], float newError)
{
  for(int i = 0; i < AVERAGE_COUNT - 1; i++)
  {
    values[i + 1] = values[i];
  }

  values[0] = newError;

  for(int i = 0; i < AVERAGE_COUNT; i++)
  {
    //Serial.print(values[i]);
  }

  //Serial.println();
}

float linInterpolate(const float gains[GAIN_POINTS], float speed)
{
  int index = (int)(speed) - 1;

  Serial.print(index);
  Serial.print("  ");

  if (index >= GAIN_POINTS - 1)
  {
    Serial.println(gains[GAIN_POINTS - 1]);
    return gains[GAIN_POINTS - 1];
  }

  if (index <= 0)
  {
    Serial.println(gains[0]);
    return gains[0];
  }

  float gain = gains [index] + ((gains [index + 1] - gains [index])*(speed - index));

  Serial.println(gain);

  return gain;