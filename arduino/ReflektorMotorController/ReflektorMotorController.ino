#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <stdlib.h>
#include <string.h>

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
const uint8_t SERIAL_BUFFER_SIZE = 32;
const unsigned long SERIAL_COMMAND_TIMEOUT_MS = 250;

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

bool motorEncendido[MOTOR_COUNT] = {false};
char serialBuffer[SERIAL_BUFFER_SIZE];
uint8_t serialBufferIndex = 0;
unsigned long ultimoCaracterSerialMs = 0;

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
  motorEncendido[numeroMotor - 1] = true;
  Serial.print(F("Motor "));
  Serial.print(numeroMotor);
  Serial.println(F(" ON"));
  return true;
}

bool apagarMotor(uint8_t numeroMotor) {
  if (!motorValido(numeroMotor)) {
    Serial.print(F("Motor fuera de rango: "));
    Serial.println(numeroMotor);
    return false;
  }

  mcp.digitalWrite(pinDeMotor(numeroMotor), LOW);
  motorEncendido[numeroMotor - 1] = false;
  Serial.print(F("Motor "));
  Serial.print(numeroMotor);
  Serial.println(F(" OFF"));
  return true;
}

void apagarTodos() {
  for (uint8_t motor = 1; motor <= MOTOR_COUNT; motor++) {
    mcp.digitalWrite(pinDeMotor(motor), LOW);
    motorEncendido[motor - 1] = false;
  }
  Serial.println(F("Todos los motores OFF"));
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
    motorEncendido[i] = false;
  }
}

bool alternarMotor(uint8_t numeroMotor) {
  if (!motorValido(numeroMotor)) {
    Serial.print(F("Motor fuera de rango: "));
    Serial.println(numeroMotor);
    return false;
  }

  if (motorEncendido[numeroMotor - 1]) {
    return apagarMotor(numeroMotor);
  }

  return encenderMotor(numeroMotor);
}

void imprimirAyudaSerial() {
  Serial.println(F("Comandos Serial:"));
  Serial.println(F("  1..12      -> alternar motor ON/OFF"));
  Serial.println(F("  on N       -> encender motor N"));
  Serial.println(F("  off N      -> apagar motor N"));
  Serial.println(F("  alloff     -> apagar todos"));
  Serial.println(F("  status     -> mostrar estado"));
  Serial.println(F("  test       -> ejecutar secuencia de prueba"));
  Serial.println(F("  help       -> mostrar esta ayuda"));
}

void imprimirEstadoMotores() {
  Serial.println(F("Estado motores:"));
  for (uint8_t motor = 1; motor <= MOTOR_COUNT; motor++) {
    Serial.print(F("  Motor "));
    Serial.print(motor);
    Serial.print(F(": "));
    Serial.println(motorEncendido[motor - 1] ? F("ON") : F("OFF"));
  }
}

uint8_t leerNumeroMotor(const char *texto) {
  int numero = atoi(texto);

  if (numero < 1 || numero > MOTOR_COUNT) {
    return 0;
  }

  return (uint8_t)numero;
}

void procesarComandoSerial(char *comando) {
  while (*comando == ' ' || *comando == '\t') {
    comando++;
  }

  if (*comando == '\0') {
    return;
  }

  for (char *p = comando; *p != '\0'; p++) {
    if (*p >= 'A' && *p <= 'Z') {
      *p = *p + ('a' - 'A');
    }
  }

  uint8_t motor = leerNumeroMotor(comando);
  if (motor != 0) {
    alternarMotor(motor);
    return;
  }

  if (strncmp(comando, "on ", 3) == 0) {
    motor = leerNumeroMotor(comando + 3);
    if (motor != 0) {
      encenderMotor(motor);
    } else {
      Serial.println(F("Uso: on N, con N entre 1 y 12"));
    }
    return;
  }

  if (strncmp(comando, "off ", 4) == 0) {
    motor = leerNumeroMotor(comando + 4);
    if (motor != 0) {
      apagarMotor(motor);
    } else {
      Serial.println(F("Uso: off N, con N entre 1 y 12"));
    }
    return;
  }

  if (strcmp(comando, "alloff") == 0 || strcmp(comando, "off") == 0) {
    apagarTodos();
    return;
  }

  if (strcmp(comando, "status") == 0) {
    imprimirEstadoMotores();
    return;
  }

  if (strcmp(comando, "test") == 0) {
    ejecutarSecuenciaPrueba();
    return;
  }

  if (strcmp(comando, "help") == 0 || strcmp(comando, "?") == 0) {
    imprimirAyudaSerial();
    return;
  }

  Serial.print(F("Comando no reconocido: "));
  Serial.println(comando);
  Serial.println(F("Escribe help para ver comandos disponibles."));
}

void leerSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    ultimoCaracterSerialMs = millis();

    if (c == '\r') {
      continue;
    }

    if (c == '\n' || c == ',') {
      if (serialBufferIndex > 0) {
        serialBuffer[serialBufferIndex] = '\0';
        procesarComandoSerial(serialBuffer);
        serialBufferIndex = 0;
      }
      return;
    }

    if (serialBufferIndex < SERIAL_BUFFER_SIZE - 1) {
      serialBuffer[serialBufferIndex] = c;
      serialBufferIndex++;
    } else {
      serialBufferIndex = 0;
      Serial.println(F("Comando demasiado largo. Buffer reiniciado."));
    }
  }

  /*
    Algunos monitores serie pueden estar configurados como "No line ending".
    En ese caso procesamos el comando cuando dejan de llegar caracteres.
  */
  if (serialBufferIndex > 0 && millis() - ultimoCaracterSerialMs > SERIAL_COMMAND_TIMEOUT_MS) {
    serialBuffer[serialBufferIndex] = '\0';
    procesarComandoSerial(serialBuffer);
    serialBufferIndex = 0;
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
  imprimirAyudaSerial();
}

void loop() {
  leerSerial();
}
