# Prueba de espejo con cámara y 12 motores

Esta prueba abre una única ventana con selector de cámara, vista de vídeo, detección de cara y estado Serial. Divide la imagen en 12 celdas. Las celdas cubiertas por la cara se envían al Arduino como una máscara Serial.

## Mapeo zigzag por defecto

La matriz por defecto es de 4 columnas × 3 filas:

```text
1   2   3   4
8   7   6   5
9  10  11  12
```

Esto coincide con un cableado físico en zigzag: la segunda fila va invertida.

## Firmware requerido

Subir `arduino/ReflektorMotorController/ReflektorMotorController.ino`.

El firmware acepta:

```text
mask 100000000001
```

Cada bit corresponde a un motor:

- `1`: motor encendido.
- `0`: motor apagado.

Ejemplo:

```text
mask 100000000001
```

enciende motores 1 y 12, apaga el resto.

## Instalación en PC

Desde la raíz del repo:

```powershell
cd "D:\CODE CODEX\REFLEKTOR"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r desktop\requirements.txt
```

## Buscar puerto Serial

```powershell
python desktop\face_motor_mirror.py --list-ports
```

## Ejecutar

Sustituir `COM3` por el puerto real:

```powershell
python desktop\face_motor_mirror.py --port COM3
```

La app muestra en la parte superior un selector de cámara. En Windows intenta mostrar el nombre del dispositivo junto al índice OpenCV, por ejemplo `0 - Integrated Camera`.

El índice sigue siendo necesario porque OpenCV abre cámaras por número. Si Windows devuelve los nombres en otro orden, prueba otro índice desde el mismo selector.

Pulsa `Start` para abrir la cámara seleccionada. Pulsa `Stop` o cierra la ventana para enviar `mask 000000000000`.

El script espera 10 segundos al abrir el puerto Serial porque el Arduino Nano normalmente se resetea al abrir el puerto y ejecuta la secuencia inicial del firmware. Si desactivas esa secuencia en el futuro, puedes reducirlo:

```powershell
python desktop\face_motor_mirror.py --port COM3 --startup-delay 2
```

## Parámetros útiles

```powershell
python desktop\face_motor_mirror.py --port COM3 --coverage 0.08
```

Menor `coverage` activa más celdas con menos área de cara.

```powershell
python desktop\face_motor_mirror.py --port COM3 --no-mirror
```

Desactiva el espejo horizontal de cámara.

```powershell
python desktop\face_motor_mirror.py --port COM3 --camera 1
```

Preselecciona la cámara `1` al abrir la ventana.

```powershell
python desktop\face_motor_mirror.py --dry-run
```

No abre Serial. Sirve para ver en consola qué máscaras enviaría.

## Notas de alimentación

Esta prueba puede encender varios motores a la vez. Si el Arduino se reinicia, el problema suele ser caída de tensión o ruido de motores:

- no alimentar motores desde el pin 5 V del Arduino;
- usar fuente externa con margen;
- GND común sólido;
- condensador electrolítico en línea de motores;
- diodos flyback correctos;
- cables I²C cortos.
