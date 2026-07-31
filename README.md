# REFLEKTOR

Proyecto Arduino para controlar 12 micromotores DC de forma independiente con:

- Arduino Nano clásico ATmega328P a 5 V.
- Módulo MCP23017 por I²C, normalmente detectado en `0x20`.
- 12 salidas ON/OFF hacia MOSFET N-channel logic-level.

No se alimentan motores desde el pin de 5 V del Arduino. Los motores usan una fuente externa de 4,5-5 V con GND común.

## Estructura

- `arduino/ReflektorMotorController/ReflektorMotorController.ino`: firmware principal.
- `arduino/I2CScanner/I2CScanner.ino`: escáner I²C independiente.
- `desktop/camera_selector_app.py`: primera app de escritorio para seleccionar y previsualizar cámaras.
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
3. Confirmar la dirección detectada. En muchos módulos MCP23017 será `0x20`.
4. Cablear un canal de motor y probarlo.
5. Replicar los 12 canales.
6. Cargar `arduino/ReflektorMotorController/ReflektorMotorController.ino`.

## Control por Monitor Serial

En el sketch principal, abrir el Monitor Serial a `115200` baudios y enviar comandos terminados en nueva línea:

- `1` a `12`: alterna el motor indicado entre ON/OFF.
- `on 3`: enciende el motor 3.
- `off 3`: apaga el motor 3.
- `allon`: enciende todos los motores.
- `alloff`: apaga todos los motores.
- `pin 11`: alterna directamente el pin lógico 11 del MCP23017, equivalente a `B3`.
- `pinon 11`: pone directamente `B3` en HIGH.
- `pinoff 11`: pone directamente `B3` en LOW.
- `map`: muestra el mapa motor -> pin MCP23017.
- `random`: ejecuta 20 activaciones aleatorias, una por vez.
- `random 50`: ejecuta 50 activaciones aleatorias, una por vez.
- `status`: muestra el estado guardado de los 12 motores.
- `test`: repite la secuencia de prueba.
- `help`: muestra los comandos disponibles.

El código también procesa comandos si el Monitor Serial está configurado como `No line ending`, usando un pequeño timeout tras recibir caracteres. Aun así, para depurar es más claro usar `Newline`.

## App de cámara

Primera versión mínima: selector oscuro de cámara con nombres y preview.

```powershell
cd "D:\CODE CODEX\REFLEKTOR"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
.\.venv\Scripts\python.exe desktop\camera_selector_app.py
```
