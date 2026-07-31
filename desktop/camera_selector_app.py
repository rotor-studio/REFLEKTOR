from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import cv2
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
        self.photo: ImageTk.PhotoImage | None = None
        self.image_id: int | None = None

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

        self.show(frame)
        self.root.after(FRAME_DELAY_MS, self.update)

    def show(self, frame) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((width, height), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(image=image)

        x = width // 2
        y = height // 2
        if self.image_id is None:
            self.image_id = self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        else:
            self.canvas.itemconfigure(self.image_id, image=self.photo)
            self.canvas.coords(self.image_id, x, y)

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
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
