# Control de 12 micromotores DC con Arduino Nano + MCP23017

## Resumen eléctrico

El MCP23017 no alimenta ni conmuta directamente los motores. Cada pin del MCP23017 controla la puerta de un MOSFET N-channel logic-level. El MOSFET conmuta el lado negativo del motor, en configuración low-side switch.

Con esta lógica:

- GPIO del MCP23017 en `HIGH` -> gate alta -> MOSFET conduce -> motor encendido.
- GPIO del MCP23017 en `LOW` -> gate baja por pull-down -> MOSFET cortado -> motor apagado.

## Conexiones I²C principales

Con un módulo MCP23017 típico, la prueba inicial puede hacerse con 4 cables:

| Señal | Arduino Nano ATmega328P | MCP23017 |
|---|---:|---:|
| SDA | A4 | SDA |
| SCL | A5 | SCL |
| 5 V lógica | 5V | VCC |
| Tierra común | GND | GND |

Notas:

- En Arduino Nano clásico, SDA es A4 y SCL es A5.
- Todas las tierras deben estar unidas: Arduino, MCP23017 y fuente externa de motores.
- Muchos módulos ya traen pull-ups I²C, dirección por defecto y RESET resuelto en la placa.
- Si usas un chip MCP23017 suelto, no dejes flotantes los pines de dirección ni RESET. En ese caso sí hay que fijarlos externamente.
- Si el escáner I²C no detecta nada, comprobar si tu módulo necesita pull-ups de 4,7 kΩ desde SDA a 5 V y desde SCL a 5 V.

## Esquema de un canal de motor

Repetir este bloque 12 veces:

```text
MCP23017 GPIO ── 220 Ω ── Gate MOSFET N logic-level
                         │
                       10 kΩ
                         │
                        GND común

+Vmotor 4,5-5 V ── Motor ── Drain MOSFET
                          Source MOSFET ── GND común

Diodo flyback en paralelo con el motor:
  cátodo -> +Vmotor
  ánodo  -> lado negativo del motor / drain MOSFET
```

Condensadores recomendados:

- 1000 µF electrolítico entre `+Vmotor` y GND, cerca de la distribución de motores.
- 100 nF cerámico en paralelo con cada motor si hay ruido, chispas de escobillas o reinicios.
- 100 nF de desacoplo cerca de VCC/GND del MCP23017 si el módulo no lo integra.

## Tabla pin a pin de motores

La librería `Adafruit_MCP23X17` numera los pines así:

- Pines `0-7` -> puerto A -> `GPA0-GPA7`.
- Pines `8-15` -> puerto B -> `GPB0-GPB7`.

| Motor | Pin lógico librería | Pin MCP23017 | Resistencia serie gate | Pull-down gate | Etapa |
|---:|---:|---|---:|---:|---|
| 1 | 0 | GPA0 | 220 Ω | 10 kΩ | MOSFET canal 1 |
| 2 | 1 | GPA1 | 220 Ω | 10 kΩ | MOSFET canal 2 |
| 3 | 2 | GPA2 | 220 Ω | 10 kΩ | MOSFET canal 3 |
| 4 | 3 | GPA3 | 220 Ω | 10 kΩ | MOSFET canal 4 |
| 5 | 4 | GPA4 | 220 Ω | 10 kΩ | MOSFET canal 5 |
| 6 | 5 | GPA5 | 220 Ω | 10 kΩ | MOSFET canal 6 |
| 7 | 6 | GPA6 | 220 Ω | 10 kΩ | MOSFET canal 7 |
| 8 | 7 | GPA7 | 220 Ω | 10 kΩ | MOSFET canal 8 |
| 9 | 8 | GPB0 | 220 Ω | 10 kΩ | MOSFET canal 9 |
| 10 | 9 | GPB1 | 220 Ω | 10 kΩ | MOSFET canal 10 |
| 11 | 10 | GPB2 | 220 Ω | 10 kΩ | MOSFET canal 11 |
| 12 | 11 | GPB3 | 220 Ω | 10 kΩ | MOSFET canal 12 |

Los pines `GPB4-GPB7`, equivalentes a los pines lógicos `12-15`, quedan libres para ampliaciones.

## Lista de componentes

Componentes principales:

- 1 × Arduino Nano clásico, ATmega328P, 5 V.
- 1 × módulo MCP23017 I²C.
- 12 × micromotor DC 4,5 V, aproximadamente 0,12 A nominal.
- 12 × MOSFET N-channel logic-level adecuado para gate a 5 V.
- 12 × diodo flyback, por ejemplo 1N5819 Schottky o 1N400x si la velocidad de conmutación no es crítica.
- 12 × resistencia 220 Ω para gate.
- 12 × resistencia 10 kΩ pull-down gate-GND.
- 1 × fuente externa 4,5-5 V para motores, dimensionada para corriente de arranque.
- 1 × condensador electrolítico 1000 µF entre alimentación de motores y GND.
- 12 × condensador cerámico 100 nF, uno por motor si el ruido lo requiere.
- Cables, bornes o placa de distribución de alimentación.

Recomendado:

- 1 × resistencia 10 kΩ pull-up para RESET del MCP23017 solo si el módulo no la integra.
- 2 × resistencias 4,7 kΩ pull-up I²C solo si el módulo no las integra.
- Fusible o limitación de corriente en la fuente de motores.

## Dimensionado de corriente

La corriente nominal total aproximada es:

```text
12 motores × 0,12 A = 1,44 A nominal
```

La corriente de arranque de micromotores DC puede ser varias veces la nominal. La fuente de motores debe tener margen suficiente. Como punto de partida práctico, usar una fuente de 4,5-5 V con al menos 3 A, y subir el margen si los motores arrancan todos a la vez o se bloquean mecánicamente.

## Fallos típicos

### El escáner I²C no encuentra el MCP23017

- SDA/SCL invertidos.
- En Nano clásico, SDA debe ir a A4 y SCL a A5.
- La dirección real del módulo no coincide con la usada en el código. Usar el escáner I²C.
- Falta GND común.
- En chip suelto o módulos incompletos: RESET flotante/bajo, dirección flotante o falta de pull-ups I²C.

### Motores no giran

- La fuente externa de motores no está conectada o no comparte GND.
- MOSFET no es logic-level y no conduce bien con gate a 5 V.
- Source/drain del MOSFET invertidos.
- Diodo flyback colocado al revés o en cortocircuito.
- El pin lógico no corresponde al pin físico esperado.

### El Arduino se reinicia

- Caída de tensión por picos de arranque de los motores.
- Fuente de motores insuficiente.
- Ruido eléctrico de escobillas acoplado a GND o líneas I²C.
- Cableado largo sin desacoplo.

Mitigaciones:

- No alimentar los motores desde el pin 5 V del Arduino.
- Usar fuente externa con margen de corriente.
- Añadir 1000 µF en la línea de motores.
- Añadir 100 nF en motores problemáticos.
- Mantener cables I²C cortos y con GND común sólido.
- Separar físicamente cableado de motores y señales I²C cuando sea posible.

### Sobrecorriente

- Un motor bloqueado puede consumir mucho más que 0,12 A.
- Doce motores arrancando a la vez pueden superar la capacidad de la fuente.
- Si hay calentamiento de MOSFET, cables o fuente, parar y medir corriente.

## Limitación del MCP23017 para PWM

El MCP23017 no tiene generadores PWM hardware. Sus pines son GPIO digitales controlados por I²C. Para hacer PWM en 12 canales habría que actualizar estados por software a través del bus I²C, lo que introduce:

- frecuencia PWM baja o irregular;
- jitter por latencia I²C y por el resto del programa;
- carga adicional para el Arduino;
- posibles parpadeos o ruido audible en motores.

Para ON/OFF independiente es adecuado. Para PWM real en 12 motores, conviene usar drivers o controladores con PWM hardware, o microcontroladores con suficientes temporizadores/salidas PWM.
