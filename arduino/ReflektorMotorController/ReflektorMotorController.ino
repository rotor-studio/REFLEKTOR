#include <Wire.h>
#include <Adafruit_MCP23X17.h>

/*
  REFLEKTOR - Control ON/OFF de 12 micromotores DC

  Hardware:
  - Arduino Nano clásico ATmega328P, 5 V.
  - Modulo MCP23017 en I2C, normalmente en direccion 0x20.
  - SDA MCP23017 -> A4 Arduino Nano.
  - SCL MCP23017 -> A5 Arduino Nano.
  - Cada salida MCP23017 controla la gate de un MOSFET N-channel logic-level.

  Mapeo confirmado para Adafruit_MCP23X17:
  - Pines 0-7  -> GPA0-GPA7.
  - Pines 8-15 -> GPB0-GPB7.

  Lógica de los MOSFET low-side:
  - HIGH en GPIO -> MOSFET conduce -> motor encendido.
  - LOW en GPIO  -> MOSFET cortado -> motor apagado.
*/

Adafruit_MCP23X17 mcp;

const uint8_t MCP23017_ADDRESS = 0x20;
const uint8_t MOTOR_COUNT = 12;
const unsigned long TEST_ON_TIME_MS = 500;

// motorPins[0] corresponde al motor 1.
// 0-7 = GPA0-GPA7, 8-11 = GPB0-GPB3.
const uint8_t motorPins[MOTOR_COUNT] = {
  0,  // Motor 1  -> GPA0
  1,  // Motor 2  -> GPA1
  2,  // Motor 3  -> GPA2
  3,  // Motor 4  -> GPA3
  4,  // Motor 5  -> GPA4
  5,  // Motor 6  -> GPA5
  6,  // Motor 7  -> GPA6
  7,  // Motor 8  -> GPA7
  8,  // Motor 9  -> GPB0
  9,  // Motor 10 -> GPB1
  10, // Motor 11 -> GPB2
  11  // Motor 12 -> GPB3
};

bool motorValido(uint8_t numeroMotor) {
  return numeroMotor >= 1 && numeroMotor <= MOTOR_COUNT;
}

uint8_t pinDeMotor(uint8_t numeroMotor) {
  return motorPins[numeroMotor - 1];
}

bool encenderMotor(uint8_t numeroMotor) {
  if (!motorValido(numeroMotor)) {
    Serial.print(F("Motor fuera de rango: "));
    Serial.println(numeroMotor);
    return false;
  }

  mcp.digitalWrite(pinDeMotor(numeroMotor), HIGH);
  return true;
}

bool apagarMotor(uint8_t numeroMotor) {
  if (!motorValido(numeroMotor)) {
    Serial.print(F("Motor fuera de rango: "));
    Serial.println(numeroMotor);
    return false;
  }

  mcp.digitalWrite(pinDeMotor(numeroMotor), LOW);
  return true;
}

void apagarTodos() {
  for (uint8_t motor = 1; motor <= MOTOR_COUNT; motor++) {
    mcp.digitalWrite(pinDeMotor(motor), LOW);
  }
}

void encenderGrupo(const uint8_t lista[], uint8_t cantidad) {
  for (uint8_t i = 0; i < cantidad; i++) {
    encenderMotor(lista[i]);
  }
}

void configurarSalidasSeguras() {
  /*
    Inicialización segura:
    1. Configurar cada pin usado como OUTPUT.
    2. Forzar LOW inmediatamente.

    El pull-down físico de 10 kΩ en cada gate mantiene los MOSFET apagados
    mientras el Arduino arranca o si el MCP23017 aún no está configurado.
  */
  for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
    mcp.pinMode(motorPins[i], OUTPUT);
    mcp.digitalWrite(motorPins[i], LOW);
  }
}

void ejecutarSecuenciaPrueba() {
  Serial.println(F("Secuencia de prueba: motores 1-12, 500 ms cada uno."));

  apagarTodos();
  delay(250);

  for (uint8_t motor = 1; motor <= MOTOR_COUNT; motor++) {
    Serial.print(F("Motor "));
    Serial.println(motor);

    encenderMotor(motor);
    delay(TEST_ON_TIME_MS);
    apagarMotor(motor);
    delay(150);
  }

  apagarTodos();
  Serial.println(F("Secuencia finalizada. Todos los motores apagados."));
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println(F("REFLEKTOR - Controlador 12 motores MCP23017"));
  Serial.println(F("Arduino Nano: SDA=A4, SCL=A5"));

  Wire.begin();

  if (!mcp.begin_I2C(MCP23017_ADDRESS)) {
    Serial.println(F("ERROR: MCP23017 no detectado en 0x20."));
    Serial.println(F("Revisar SDA=A4, SCL=A5, VCC=5V, GND comun y direccion real con el escaner I2C."));

    // No continuar si no existe el expansor: evita estados inesperados.
    while (true) {
      delay(1000);
    }
  }

  Serial.println(F("MCP23017 detectado en 0x20."));

  configurarSalidasSeguras();
  ejecutarSecuenciaPrueba();
}

void loop() {
  /*
    Preparado para futuras secuencias.

    Ejemplo:
      uint8_t grupo[] = {1, 4, 9};
      encenderGrupo(grupo, 3);
      delay(1000);
      apagarTodos();
  */
}
