#include <Servo.h>

// --- DEFINICIÓN DE PINES ---
// Servomotores (pueden usar cualquier pin digital)
const int pinServo1 = 8;
const int pinServo2 = 12;

// Motor DC (Driver L298N)
const int pinMotorPWM = 3;  // Pin ENA (PWM para velocidad)
const int pinMotorIN1 = 2;  // Pin IN1 (Dirección)
const int pinMotorIN2 = 4;  // Pin IN2 (Dirección)

// LEDs (Deben ser pines PWM soportados: 3, 5, 6, 11 al usar Servo.h)
const int pinLed1 = 5;
const int pinLed2 = 6;

// --- OBJETOS Y VARIABLES ---
Servo servo1;
Servo servo2;

int numeroDerecha = 0;
int porcentajeIzquierda = 0;

void setup() {
  Serial.begin(9600);
  
  // Configurar servos
  servo1.attach(pinServo1);
  servo2.attach(pinServo2);
  
  // Posición inicial de servos (0 grados)
  servo1.write(0);
  servo2.write(0);
  
  // Configurar Motor DC
  pinMode(pinMotorPWM, OUTPUT);
  pinMode(pinMotorIN1, OUTPUT);
  pinMode(pinMotorIN2, OUTPUT);
  
  // Configurar dirección fija del motor hacia adelante
  digitalWrite(pinMotorIN1, HIGH);
  digitalWrite(pinMotorIN2, LOW);
  analogWrite(pinMotorPWM, 0); // Apagado inicialmente
  
  // Configurar LEDs
  pinMode(pinLed1, OUTPUT);
  pinMode(pinLed2, OUTPUT);
  analogWrite(pinLed1, 0);
  analogWrite(pinLed2, 0);
}
void loop() {
  if (Serial.available() > 0) {
    numeroDerecha = Serial.parseInt();
    porcentajeIzquierda = Serial.parseInt();
    
    while (Serial.available() > 0 && Serial.read() != '\n') {}

    int anguloServo = map(porcentajeIzquierda, 0, 100, 0, 180);
    int valorPWM = map(porcentajeIzquierda, 0, 100, 0, 255);

    // 1. Control Activo
    switch (numeroDerecha) {
      case 1:
        servo1.write(anguloServo);
        break;
      case 2:
        servo2.write(anguloServo);
        break;
      case 3:
        analogWrite(pinMotorPWM, valorPWM);
        break;
      case 4:
        analogWrite(pinLed1, valorPWM);
        break;
      case 5:
        if(porcentajeIzquierda >= 50){
          digitalWrite(pinLed2, HIGH);
        } else{
          digitalWrite(pinLed2, LOW);
        }
        break;
    }

    // 2. Apagado de seguridad para Motor y LEDs al cambiar de gesto o cerrar el puño
    if (numeroDerecha != 3) {
      analogWrite(pinMotorPWM, 0); // Apaga el motor si no estás mostrando 3 dedos
    }
    if (numeroDerecha != 4) {
      analogWrite(pinLed1, 0);     // Apaga LED 1 si no estás mostrando 4 dedos
    }
    if (numeroDerecha != 5) {
      analogWrite(pinLed2, 0);     // Apaga LED 2 si no estás mostrando 5 dedos
    }
  }
}