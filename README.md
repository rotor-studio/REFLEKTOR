# REFLEKTOR

Proyecto Arduino para controlar 12 micromotores DC de forma independiente con:

- Arduino Nano clásico ATmega328P a 5 V.
- Expansor MCP23017 por I²C en dirección inicial `0x20`.
- 12 salidas ON/OFF hacia MOSFET N-channel logic-level.

No se alimentan motores desde el pin de 5 V del Arduino. Los motores usan una fuente externa de 4,5-5 V con GND común.

## Estructura

- `arduino/ReflektorMotorController/ReflektorMotorController.ino`: firmware principal.
- `arduino/I2CScanner/I2CScanner.ino`: escáner I²C independiente.
- `docs/hardware_12_motores_mcp23017.md`: esquema de conexiones, tabla pin a pin, componentes y fallos típicos.

## Librerías Arduino necesarias

Instalar desde el Library Manager del Arduino IDE:

- `Adafruit MCP23017 Arduino Library`
- `Adafruit BusIO`

El firmware usa:

```cpp
#include <Wire.h>
#include <Adafruit_MCP23X17.h>
```

Nota: en el Library Manager hay que buscar `Adafruit MCP23017`, no `Adafruit_MCP23X17`. `Adafruit_MCP23X17.h` es el archivo incluido por la librería actual de Adafruit.

## Flujo recomendado

1. Cablear solo Arduino Nano + MCP23017.
2. Cargar `arduino/I2CScanner/I2CScanner.ino`.
3. Confirmar que aparece `0x20`.
4. Cablear un canal de motor y probarlo.
5. Replicar los 12 canales.
6. Cargar `arduino/ReflektorMotorController/ReflektorMotorController.ino`.
