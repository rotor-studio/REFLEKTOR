from __future__ import annotations

from pathlib import Path
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image, ImageTk
import serial
from serial.tools import list_ports


WINDOW_TITLE = "REFLEKTOR"
BG = "#101010"
FG = "#e8e8e8"
ERROR = "#ff5c7a"
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
FRAME_DELAY_MS = 33
SERIAL_BAUD = 115200
GRID_ROWS = 4
GRID_COLS = 3
GRID_MARGIN_RATIO = 0.12
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"
FINGERTIPS = [
    (4, "pulgar"),
    (8, "indice"),
    (12, "corazon"),
    (16, "anular"),
    (20, "menique"),
]


@dataclass(frozen=True)
class DisplaySize:
    width: int
    height: int


@dataclass(frozen=True)
class GridRect:
    x: float
    y: float
    width: float
    height: float


CAMERAS = [
    "0 - Camara 0",
    "1 - Camara 1",
    "2 - Microsoft LifeCam Studio",
    "3 - Camara 3",
]


def camera_index_from_label(label: str) -> int:
    try:
        return int(label.split("-", 1)[0].strip())
    except Exception:
        return 2


def serial_ports() -> list[str]:
    ports = [f"{port.device} - {port.description}" for port in list_ports.comports()]
    return ports or ["sin puertos"]


def port_name_from_label(label: str) -> str | None:
    if label == "sin puertos":
        return None
    return label.split(" - ", 1)[0].strip()


def ensure_hand_model() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("980x620")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.selected_camera = tk.StringVar(value=CAMERAS[2])
        self.selected_port = tk.StringVar(value=serial_ports()[0])
        self.serial_connection: serial.Serial | None = None

        self.top = tk.Frame(root, bg=BG)
        self.top.pack(fill=tk.X, padx=8, pady=8)

        self.camera_combo = self.combo(self.top, self.selected_camera, CAMERAS, 34)
        self.camera_combo.pack(side=tk.LEFT, padx=(0, 6))

        self.select_camera_button = tk.Button(
            self.top,
            text="seleccionar",
            command=self.restart_camera,
            bg="#202020",
            fg=FG,
            activebackground="#303030",
            activeforeground=FG,
            bd=0,
            padx=8,
            pady=3,
        )
        self.select_camera_button.pack(side=tk.LEFT, padx=(0, 6))

        self.port_combo = self.combo(self.top, self.selected_port, serial_ports(), 38)
        self.port_combo.pack(side=tk.LEFT, padx=(0, 6))

        self.refresh_button = tk.Button(
            self.top,
            text="refrescar puertos",
            command=self.refresh_ports,
            bg="#202020",
            fg=FG,
            activebackground="#303030",
            activeforeground=FG,
            bd=0,
            padx=8,
            pady=3,
        )
        self.refresh_button.pack(side=tk.LEFT)

        self.connect_button = tk.Button(
            self.top,
            text="conectar",
            command=self.toggle_serial,
            bg="#202020",
            fg=FG,
            activebackground="#303030",
            activeforeground=FG,
            bd=0,
            padx=8,
            pady=3,
        )
        self.connect_button.pack(side=tk.LEFT, padx=(6, 0))

        self.status = tk.Label(self.top, text="", bg=BG, fg=FG)
        self.status.pack(side=tk.LEFT, padx=(8, 0))

        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.cap: cv2.VideoCapture | None = self.open_selected_camera()
        model_path = ensure_hand_model()
        self.hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6,
            )
        )
        self.photo: ImageTk.PhotoImage | None = None
        self.image_id: int | None = None
        self.hover_cell: tuple[int, int] | None = None
        self.active_motors: set[int] = set()
        self.fingertips: list[tuple[str, int, int]] = []

        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", self.on_mouse_leave)

        if self.cap is None or not self.cap.isOpened():
            self.error("no se pudo abrir la camara")
            return

        self.update()

    def combo(self, parent, variable: tk.StringVar, values: list[str], width: int) -> ttk.Combobox:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground="#181818",
            background="#181818",
            foreground=FG,
            arrowcolor=FG,
            bordercolor="#333333",
            lightcolor="#333333",
            darkcolor="#333333",
        )
        return ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            width=width,
            state="readonly",
            style="Dark.TCombobox",
        )

    def open_selected_camera(self) -> cv2.VideoCapture:
        index = camera_index_from_label(self.selected_camera.get())
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        return cap

    def restart_camera(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = self.open_selected_camera()
        if not self.cap.isOpened():
            self.error("no se pudo abrir la camara")

    def refresh_ports(self) -> None:
        ports = serial_ports()
        self.port_combo.configure(values=ports)
        self.selected_port.set(ports[0])

    def toggle_serial(self) -> None:
        if self.serial_connection is not None:
            self.serial_connection.close()
            self.serial_connection = None
            self.connect_button.configure(text="conectar")
            self.status.configure(text="desconectado")
            return

        port_name = port_name_from_label(self.selected_port.get())
        if port_name is None:
            self.status.configure(text="sin puerto")
            return

        try:
            self.serial_connection = serial.Serial(port_name, SERIAL_BAUD, timeout=0.1)
        except serial.SerialException as exc:
            self.serial_connection = None
            self.status.configure(text=f"error {port_name}")
            print(exc)
            return

        self.connect_button.configure(text="desconectar")
        self.status.configure(text=f"conectado {port_name}")

    def update(self) -> None:
        if self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.error("sin imagen")
            self.root.after(250, self.update)
            return

        frame = cv2.flip(frame, 1)
        self.process_hand_gesture(frame)
        self.show(frame)
        self.root.after(FRAME_DELAY_MS, self.update)

    def process_hand_gesture(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.hands.detect(mp_image)

        if not result.hand_landmarks:
            self.update_active_motors(set())
            self.fingertips = []
            return

        landmarks = result.hand_landmarks[0]
        frame_height, frame_width = frame.shape[:2]
        self.fingertips = [
            (
                label,
                int(landmarks[index].x * frame_width),
                int(landmarks[index].y * frame_height),
            )
            for index, label in FINGERTIPS
        ]

        active_motors: set[int] = set()
        for _label, x, y in self.fingertips:
            canvas_width = max(1, self.canvas.winfo_width())
            canvas_height = max(1, self.canvas.winfo_height())
            canvas_x = int((x / frame_width) * canvas_width)
            canvas_y = int((y / frame_height) * canvas_height)
            cell = self.cell_from_position(canvas_x, canvas_y)
            if cell is not None:
                row, col = cell
                active_motors.add(self.motor_for_cell(row, col))

        self.update_active_motors(active_motors)

    def update_active_motors(self, new_active_motors: set[int]) -> None:
        if new_active_motors == self.active_motors:
            return

        for motor in sorted(self.active_motors - new_active_motors):
            self.send_motor_state(motor, False)
        for motor in sorted(new_active_motors - self.active_motors):
            self.send_motor_state(motor, True)

        self.active_motors = set(new_active_motors)

    def show(self, frame) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = self.cover_resize(image, DisplaySize(width, height))
        self.photo = ImageTk.PhotoImage(image=image)

        x = width // 2
        y = height // 2
        if self.image_id is None:
            self.image_id = self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        else:
            self.canvas.itemconfigure(self.image_id, image=self.photo)
            self.canvas.coords(self.image_id, x, y)

        self.draw_grid(width, height)
        self.draw_fingertips(width, height)

    def draw_grid(self, width: int, height: int) -> None:
        self.canvas.delete("grid")
        grid = self.grid_rect(width, height)
        cell_width = grid.width / GRID_COLS
        cell_height = grid.height / GRID_ROWS

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                motor = self.motor_for_cell(row, col)
                x1 = grid.x + col * cell_width
                y1 = grid.y + row * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height
                active = motor in self.active_motors
                hovered = self.hover_cell == (row, col)

                if active:
                    self.canvas.create_rectangle(
                        x1,
                        y1,
                        x2,
                        y2,
                        fill="#ff8c00",
                        stipple="gray50",
                        outline="",
                        tags="grid",
                    )

                if hovered:
                    self.canvas.create_rectangle(
                        x1,
                        y1,
                        x2,
                        y2,
                        fill="#000000",
                        stipple="gray50",
                        outline="",
                        tags="grid",
                    )

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    outline="#ffffff",
                    width=1,
                    tags="grid",
                )
                self.canvas.create_text(
                    x1 + 14,
                    y1 + 14,
                    text=str(motor),
                    fill="#ffffff",
                    anchor=tk.NW,
                    font=("Segoe UI", 12),
                    tags="grid",
                )

    def motor_for_cell(self, row: int, col: int) -> int:
        if row % 2 == 0:
            return row * GRID_COLS + col + 1
        return row * GRID_COLS + (GRID_COLS - col)

    def cell_from_position(self, x: int, y: int) -> tuple[int, int] | None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        grid = self.grid_rect(width, height)

        if x < grid.x or y < grid.y or x >= grid.x + grid.width or y >= grid.y + grid.height:
            return None

        col = min(GRID_COLS - 1, int((x - grid.x) / (grid.width / GRID_COLS)))
        row = min(GRID_ROWS - 1, int((y - grid.y) / (grid.height / GRID_ROWS)))
        return row, col

    def grid_rect(self, width: int, height: int) -> GridRect:
        margin = min(width, height) * GRID_MARGIN_RATIO
        available_width = max(1, width - margin * 2)
        available_height = max(1, height - margin * 2)

        # Mantiene la proporción 3:4 de la rejilla para que las celdas sean cuadradas.
        target_ratio = GRID_COLS / GRID_ROWS
        available_ratio = available_width / available_height

        if available_ratio > target_ratio:
            grid_height = available_height
            grid_width = grid_height * target_ratio
        else:
            grid_width = available_width
            grid_height = grid_width / target_ratio

        return GridRect(
            x=(width - grid_width) / 2,
            y=(height - grid_height) / 2,
            width=grid_width,
            height=grid_height,
        )

    def on_mouse_move(self, event) -> None:
        if self.fingertips:
            return

        self.hover_cell = self.cell_from_position(event.x, event.y)

        active_motors: set[int] = set()
        if self.hover_cell is not None:
            row, col = self.hover_cell
            active_motors.add(self.motor_for_cell(row, col))

        self.update_active_motors(active_motors)
        self.draw_grid(max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))

    def on_mouse_leave(self, _event) -> None:
        if self.fingertips:
            return

        self.update_active_motors(set())
        self.hover_cell = None
        self.draw_grid(max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))

    def send_motor_state(self, motor: int, active: bool) -> None:
        command = f"{'on' if active else 'off'} {motor}\n"
        if self.serial_connection is not None:
            self.serial_connection.write(command.encode("ascii"))
        self.status.configure(text=f"motor {motor} {'on' if active else 'off'}")

    def draw_fingertips(self, width: int, height: int) -> None:
        self.canvas.delete("fingertip")
        for _label, source_x, source_y in self.fingertips:
            x = int((source_x / CAMERA_WIDTH) * width)
            y = int((source_y / CAMERA_HEIGHT) * height)
            radius = 6

            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="",
                outline="#ff3333",
                width=2,
                tags="fingertip",
            )

    def cover_resize(self, image: Image.Image, target: DisplaySize) -> Image.Image:
        source_width, source_height = image.size
        scale = max(target.width / source_width, target.height / source_height)
        resized_width = max(1, int(source_width * scale))
        resized_height = max(1, int(source_height * scale))

        image = image.resize((resized_width, resized_height), Image.Resampling.BILINEAR)

        left = max(0, (resized_width - target.width) // 2)
        top = max(0, (resized_height - target.height) // 2)
        right = left + target.width
        bottom = top + target.height
        return image.crop((left, top, right, bottom))

    def error(self, text: str) -> None:
        self.canvas.delete("all")
        self.image_id = None
        self.canvas.create_text(
            max(1, self.canvas.winfo_width()) // 2,
            max(1, self.canvas.winfo_height()) // 2,
            text=text,
            fill=ERROR,
            font=("Segoe UI", 12),
        )

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.serial_connection is not None:
            self.serial_connection.close()
            self.serial_connection = None
        self.hands.close()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
