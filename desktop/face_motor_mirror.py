"""
REFLEKTOR - Face motor mirror

Abre una camara, detecta una cara con OpenCV, divide la imagen en una matriz
de 12 celdas en zigzag y envia una mascara Serial al firmware Arduino:

    mask 100000000001

Mapeo por defecto, 4 columnas x 3 filas:

    fila 0: motor  1,  2,  3,  4
    fila 1: motor  8,  7,  6,  5
    fila 2: motor  9, 10, 11, 12

Uso:
    python desktop/face_motor_mirror.py --port COM3
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Iterable
import tkinter as tk
from tkinter import ttk

import cv2
import serial
from serial.tools import list_ports


MOTOR_COUNT = 12


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta cara y controla 12 motores por Serial en formato zigzag."
    )
    parser.add_argument("--port", help="Puerto Serial del Arduino, por ejemplo COM3.")
    parser.add_argument("--baud", type=int, default=115200, help="Baudios Serial.")
    parser.add_argument(
        "--camera",
        type=int,
        help="Indice de camara OpenCV. Si se omite, la app muestra un selector.",
    )
    parser.add_argument(
        "--max-cameras",
        type=int,
        default=10,
        help="Cantidad de indices de camara a probar en el selector, empezando en 0.",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=10.0,
        help="Espera tras abrir Serial. El Nano suele resetearse al abrir el puerto.",
    )
    parser.add_argument("--cols", type=int, default=4, help="Columnas de la matriz.")
    parser.add_argument("--rows", type=int, default=3, help="Filas de la matriz.")
    parser.add_argument(
        "--coverage",
        type=float,
        default=0.12,
        help="Fraccion minima de celda cubierta por la cara para activar motor.",
    )
    parser.add_argument(
        "--send-interval",
        type=float,
        default=0.08,
        help="Intervalo minimo entre envios Serial, en segundos.",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="No invertir horizontalmente la camara. Por defecto actua como espejo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No abre Serial; solo muestra la mascara en consola.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Lista puertos Serial disponibles y sale.",
    )
    return parser.parse_args()


def list_serial_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No se encontraron puertos Serial.")
        return

    for port in ports:
        print(f"{port.device}: {port.description}")


def open_camera(index: int) -> cv2.VideoCapture:
    return cv2.VideoCapture(index)


def select_camera_interactively(max_cameras: int) -> int | None:
    camera_values = [str(index) for index in range(max(1, max_cameras))]

    selected_camera: int | None = None

    root = tk.Tk()
    root.title("REFLEKTOR - seleccionar camara")
    root.geometry("420x210")
    root.resizable(False, False)

    tk.Label(
        root,
        text="Selecciona la camara para la prueba REFLEKTOR",
        font=("Segoe UI", 11),
    ).pack(pady=(18, 8))

    selected_value = tk.StringVar(value=camera_values[0])

    combo = ttk.Combobox(root, values=camera_values, textvariable=selected_value, state="readonly")
    combo.pack(pady=8)
    combo.focus_set()

    info = "Prueba primero 0. Si no es la correcta, cierra y elige otro indice."
    tk.Label(root, text=info, font=("Segoe UI", 9)).pack(pady=(4, 12))

    def accept() -> None:
        nonlocal selected_camera
        selected_camera = int(selected_value.get())
        root.destroy()

    def cancel() -> None:
        root.destroy()

    button_frame = tk.Frame(root)
    button_frame.pack(pady=8)
    ttk.Button(button_frame, text="Usar camara", command=accept).pack(side=tk.LEFT, padx=8)
    ttk.Button(button_frame, text="Cancelar", command=cancel).pack(side=tk.LEFT, padx=8)

    root.bind("<Return>", lambda _event: accept())
    root.bind("<Escape>", lambda _event: cancel())
    root.mainloop()

    return selected_camera


def zigzag_motor_for_cell(row: int, col: int, cols: int) -> int:
    if row % 2 == 0:
        return row * cols + col + 1
    return row * cols + (cols - col)


def intersection_area(a: Rect, b: Rect) -> int:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x + a.w, b.x + b.w)
    y2 = min(a.y + a.h, b.y + b.h)
    return max(0, x2 - x1) * max(0, y2 - y1)


def mask_from_face(
    frame_width: int,
    frame_height: int,
    face: Rect | None,
    rows: int,
    cols: int,
    min_coverage: float,
) -> str:
    states = ["0"] * MOTOR_COUNT

    if face is None:
        return "".join(states)

    cell_w = frame_width / cols
    cell_h = frame_height / rows

    for row in range(rows):
        for col in range(cols):
            cell = Rect(
                x=int(round(col * cell_w)),
                y=int(round(row * cell_h)),
                w=int(round(cell_w)),
                h=int(round(cell_h)),
            )
            motor = zigzag_motor_for_cell(row, col, cols)
            if motor < 1 or motor > MOTOR_COUNT:
                continue

            coverage = intersection_area(cell, face) / max(1, cell.area)
            if coverage >= min_coverage:
                states[motor - 1] = "1"

    return "".join(states)


def largest_face(faces: Iterable[tuple[int, int, int, int]]) -> Rect | None:
    rects = [Rect(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]
    if not rects:
        return None
    return max(rects, key=lambda rect: rect.area)


def draw_grid(frame, rows: int, cols: int, mask: str, face: Rect | None) -> None:
    height, width = frame.shape[:2]
    cell_w = width / cols
    cell_h = height / rows

    for row in range(rows):
        for col in range(cols):
            motor = zigzag_motor_for_cell(row, col, cols)
            x1 = int(round(col * cell_w))
            y1 = int(round(row * cell_h))
            x2 = int(round((col + 1) * cell_w))
            y2 = int(round((row + 1) * cell_h))
            active = 1 <= motor <= MOTOR_COUNT and mask[motor - 1] == "1"
            color = (0, 255, 0) if active else (80, 80, 80)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                str(motor),
                (x1 + 10, y1 + 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
                cv2.LINE_AA,
            )

    if face is not None:
        cv2.rectangle(
            frame,
            (face.x, face.y),
            (face.x + face.w, face.y + face.h),
            (255, 0, 0),
            2,
        )

    cv2.putText(
        frame,
        f"mask {mask}",
        (10, height - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def open_serial(port: str, baud: int, startup_delay: float) -> serial.Serial:
    arduino = serial.Serial(port=port, baudrate=baud, timeout=0.1, write_timeout=0.2)
    time.sleep(startup_delay)
    arduino.reset_input_buffer()
    return arduino


def send_mask(arduino: serial.Serial | None, mask: str, dry_run: bool) -> None:
    command = f"mask {mask}\n"
    if dry_run:
        print(command.strip())
        return

    if arduino is None:
        return

    arduino.write(command.encode("ascii"))


def main() -> int:
    args = parse_args()

    if args.list_ports:
        list_serial_ports()
        return 0

    if args.rows * args.cols != MOTOR_COUNT:
        print("Error: rows * cols debe ser 12.", file=sys.stderr)
        return 2

    if not args.dry_run and not args.port:
        print("Error: indica --port COMx o usa --list-ports.", file=sys.stderr)
        return 2

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        print(f"Error: no se pudo cargar el detector Haar: {cascade_path}", file=sys.stderr)
        return 1

    camera_index = args.camera
    if camera_index is None:
        camera_index = select_camera_interactively(args.max_cameras)
        if camera_index is None:
            return 1

    camera = open_camera(camera_index)
    if not camera.isOpened():
        print(f"Error: no se pudo abrir la camara {camera_index}.", file=sys.stderr)
        return 1

    arduino = None
    if not args.dry_run:
        arduino = open_serial(args.port, args.baud, args.startup_delay)
        print(f"Serial abierto: {args.port} @ {args.baud}")

    last_mask = ""
    last_send_time = 0.0

    print("Pulsa q en la ventana de video para salir.")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("Error: no se pudo leer frame de camara.", file=sys.stderr)
                return 1

            if not args.no_mirror:
                frame = cv2.flip(frame, 1)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )
            face = largest_face(faces)
            height, width = frame.shape[:2]
            mask = mask_from_face(width, height, face, args.rows, args.cols, args.coverage)

            now = time.monotonic()
            if mask != last_mask and now - last_send_time >= args.send_interval:
                send_mask(arduino, mask, args.dry_run)
                last_mask = mask
                last_send_time = now

            draw_grid(frame, args.rows, args.cols, mask, face)
            cv2.imshow("REFLEKTOR face motor mirror", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break

    finally:
        send_mask(arduino, "0" * MOTOR_COUNT, args.dry_run)
        if arduino is not None:
            arduino.close()
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
