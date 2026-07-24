#include <Wire.h>

/*
  Escaner I2C independiente para Arduino Nano clasico.

  Conexiones:
  - SDA -> A4
  - SCL -> A5
  - GND comun
  - MCP23017 VCC -> 5 V

  En muchos modulos MCP23017, la direccion por defecto detectada sera 0x20.
*/

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin();

  Serial.println(F("Escaner I2C"));
  Serial.println(F("Arduino Nano clasico: SDA=A4, SCL=A5"));
}

void loop() {
  byte error;
  byte address;
  int devicesFound = 0;

  Serial.println(F("Escaneando bus I2C..."));

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print(F("Dispositivo I2C encontrado en 0x"));
      if (address < 16) {
        Serial.print(F("0"));
      }
      Serial.println(address, HEX);
      devicesFound++;
    } else if (error == 4) {
      Serial.print(F("Error desconocido en 0x"));
      if (address < 16) {
        Serial.print(F("0"));
      }
      Serial.println(address, HEX);
    }
  }

  if (devicesFound == 0) {
    Serial.println(F("No se encontraron dispositivos I2C."));
  } else {
    Serial.print(F("Total de dispositivos encontrados: "));
    Serial.println(devicesFound);
  }

  Serial.println();
  delay(5000);
}
