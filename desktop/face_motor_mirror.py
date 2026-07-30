"""
REFLEKTOR - Face motor mirror

Una sola ventana:
- selector de camara con nombre;
- vista de video;
- deteccion de cara;
- cuadricula zigzag de 12 motores;
- envio Serial al firmware Arduino con comandos "mask 000000000000".
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageTk
import serial
from serial.tools import list_ports


MOTOR_COUNT = 12
VIDEO_WIDTH = 960
VIDEO_HEIGHT = 540


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)


@dataclass(frozen=True)
class CameraOption:
    index: int
    name: str

    @property
    def label(self) -> str:
        return f"{self.index} - {self.name}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta cara y controla 12 motores por Serial en formato zigzag."
    )
    parser.add_argument("--port", help="Puerto Serial del Arduino, por ejemplo COM7.")
    parser.add_argument("--baud", type=int, default=115200, help="Baudios Serial.")
    parser.add_argument("--camera", type=int, help="Indice de camara OpenCV inicial.")
    parser.add_argument(
        "--max-cameras",
        type=int,
        default=10,
        help="Cantidad de indices de camara a mostrar, empezando en 0.",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=10.0,
        help="Espera logica tras abrir Serial. El Nano suele resetearse al abrir el puerto.",
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
        help="No abre Serial; solo imprime mascara en consola.",
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


def get_windows_camera_names() -> list[str]:
    if not sys.platform.startswith("win"):
        return []

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { "
            "$_.PNPClass -eq 'Camera' -or "
            "$_.PNPClass -eq 'Image' -or "
            "$_.Name -match 'Camera|Camara|Webcam|Video' "
            "} | Select-Object -ExpandProperty Name"
        ),
    ]

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []

    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return list(dict.fromkeys(names))


def build_camera_options(max_cameras: int) -> list[CameraOption]:
    names = get_windows_camera_names()
    options: list[CameraOption] = []

    for index in range(max(1, max_cameras)):
        if index < len(names):
            name = names[index]
        else:
            name = f"Camara OpenCV {index}"
        options.append(CameraOption(index=index, name=name))

    return options


def open_camera(index: int) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(index)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
    return camera


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


class ReflektorApp:
    def __init__(self, root: tk.Tk, args: argparse.Namespace) -> None:
        self.root = root
        self.args = args
        self.camera_options = build_camera_options(args.max_cameras)
        self.camera: cv2.VideoCapture | None = None
        self.arduino: serial.Serial | None = None
        self.serial_ready_at = 0.0
        self.serial_buffer_reset_done = False
        self.running = False
        self.last_mask = ""
        self.last_send_time = 0.0
        self.photo: ImageTk.PhotoImage | None = None

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            raise RuntimeError(f"No se pudo cargar el detector Haar: {cascade_path}")

        self.root.title("REFLEKTOR - Face Motor Mirror")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.camera_by_label = {option.label: option for option in self.camera_options}
        initial_option = self.camera_options[0]
        if args.camera is not None:
            for option in self.camera_options:
                if option.index == args.camera:
                    initial_option = option
                    break

        self.selected_camera_label = tk.StringVar(value=initial_option.label)
        self.port_value = tk.StringVar(value=args.port or "COM7")
        self.status_value = tk.StringVar(value="Selecciona camara y pulsa Start.")
        self.mask_value = tk.StringVar(value="mask 000000000000")

        self.build_ui()
        self.show_placeholder("Selecciona camara y pulsa Start.")

    def build_ui(self) -> None:
        self.root.geometry("1100x760")
        self.root.minsize(900, 650)

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Camara").pack(side=tk.LEFT, padx=(0, 6))
        self.camera_combo = ttk.Combobox(
            top,
            values=[option.label for option in self.camera_options],
            textvariable=self.selected_camera_label,
            state="readonly",
            width=42,
        )
        self.camera_combo.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(top, text="Serial").pack(side=tk.LEFT, padx=(0, 6))
        self.port_entry = ttk.Entry(top, textvariable=self.port_value, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=(0, 12))

        self.start_button = ttk.Button(top, text="Start video + motores", command=self.start)
        self.start_button.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_button = ttk.Button(top, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        self.video_label = ttk.Label(self.root, anchor=tk.CENTER)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.pack(fill=tk.X)

        ttk.Label(bottom, textvariable=self.mask_value).pack(anchor=tk.W)
        ttk.Label(bottom, textvariable=self.status_value).pack(anchor=tk.W)

        help_text = (
            "Mapeo zigzag: 1 2 3 4 / 8 7 6 5 / 9 10 11 12. "
            "Cierra la ventana o pulsa Stop para enviar mask 000000000000."
        )
        ttk.Label(bottom, text=help_text).pack(anchor=tk.W)

    def show_placeholder(self, text: str) -> None:
        frame = self.placeholder_frame(text)
        self.show_frame(frame)

    def placeholder_frame(self, text: str):
        frame = np.full((VIDEO_HEIGHT, VIDEO_WIDTH, 3), 30, dtype=np.uint8)
        cv2.putText(
            frame,
            text,
            (40, VIDEO_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (230, 230, 230),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "La rejilla aparece sobre el video cuando la camara entrega frames.",
            (40, VIDEO_HEIGHT // 2 + 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (180, 180, 180),
            1,
            cv2.LINE_AA,
        )
        return frame

    def show_frame(self, frame) -> None:
        display_frame = cv2.resize(frame, (VIDEO_WIDTH, VIDEO_HEIGHT), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        self.photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(image=self.photo)

    def selected_camera_index(self) -> int:
        option = self.camera_by_label[self.selected_camera_label.get()]
        return option.index

    def start(self) -> None:
        if self.running:
            return

        camera_index = self.selected_camera_index()
        camera = open_camera(camera_index)
        if not camera.isOpened():
            camera.release()
            messagebox.showerror("Camara", f"No se pudo abrir la camara {camera_index}.")
            self.show_placeholder(f"No se pudo abrir la camara {camera_index}.")
            return

        ok, first_frame = camera.read()
        if not ok:
            camera.release()
            messagebox.showerror(
                "Camara",
                f"La camara {camera_index} se abre, pero no entrega imagen.",
            )
            self.show_placeholder(f"Camara {camera_index} sin frames. Prueba otro indice.")
            return

        self.camera = camera
        self.running = True
        self.last_mask = ""
        self.last_send_time = 0.0
        self.serial_buffer_reset_done = False

        if not self.args.dry_run:
            try:
                self.arduino = serial.Serial(
                    port=self.port_value.get(),
                    baudrate=self.args.baud,
                    timeout=0.1,
                    write_timeout=0.2,
                )
                self.serial_ready_at = time.monotonic() + self.args.startup_delay
                self.status_value.set(
                    f"Camara {camera_index} activa. Serial abierto; esperando reset Arduino."
                )
            except serial.SerialException as exc:
                self.stop(send_zero=False)
                messagebox.showerror("Serial", f"No se pudo abrir {self.port_value.get()}: {exc}")
                return
        else:
            self.status_value.set(f"Camara {camera_index} activa. Dry-run sin Serial.")

        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.camera_combo.configure(state=tk.DISABLED)
        self.port_entry.configure(state=tk.DISABLED)
        if not self.args.no_mirror:
            first_frame = cv2.flip(first_frame, 1)
        self.show_frame(first_frame)
        self.update_frame()

    def stop(self, send_zero: bool = True) -> None:
        if send_zero:
            self.send_mask("0" * MOTOR_COUNT)

        self.running = False

        if self.camera is not None:
            self.camera.release()
            self.camera = None

        if self.arduino is not None:
            self.arduino.close()
            self.arduino = None

        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.camera_combo.configure(state="readonly")
        self.port_entry.configure(state=tk.NORMAL)
        self.mask_value.set("mask 000000000000")
        self.status_value.set("Parado.")
        self.show_placeholder("Parado. Selecciona camara y pulsa Start.")

    def send_mask(self, mask: str) -> None:
        command = f"mask {mask}\n"

        if self.args.dry_run:
            print(command.strip())
            return

        if self.arduino is None:
            return

        now = time.monotonic()
        if now < self.serial_ready_at:
            return

        if not self.serial_buffer_reset_done:
            self.arduino.reset_input_buffer()
            self.serial_buffer_reset_done = True
            self.status_value.set("Serial listo. Enviando mascaras.")

        self.arduino.write(command.encode("ascii"))

    def update_frame(self) -> None:
        if not self.running or self.camera is None:
            return

        ok, frame = self.camera.read()
        if not ok:
            camera_index = self.selected_camera_index()
            self.status_value.set(f"Camara {camera_index} abierta, pero sin frames.")
            self.show_placeholder(f"Camara {camera_index} sin frames. Prueba otro indice.")
            self.root.after(100, self.update_frame)
            return

        if not self.args.no_mirror:
            frame = cv2.flip(frame, 1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        face = largest_face(faces)
        height, width = frame.shape[:2]
        mask = mask_from_face(width, height, face, self.args.rows, self.args.cols, self.args.coverage)

        now = time.monotonic()
        if mask != self.last_mask and now - self.last_send_time >= self.args.send_interval:
            self.send_mask(mask)
            self.last_mask = mask
            self.last_send_time = now

        draw_grid(frame, self.args.rows, self.args.cols, mask, face)
        self.mask_value.set(f"mask {mask}")

        self.show_frame(frame)

        self.root.after(15, self.update_frame)

    def on_close(self) -> None:
        self.stop(send_zero=True)
        self.root.destroy()


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

    root = tk.Tk()
    try:
        app = ReflektorApp(root, args)
    except RuntimeError as exc:
        messagebox.showerror("REFLEKTOR", str(exc))
        return 1

    root.mainloop()
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
