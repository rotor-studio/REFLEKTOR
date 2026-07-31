"""
REFLEKTOR - Camera selector prototype

App minima:
- tema oscuro;
- desplegable con nombres de camaras;
- preview de la camara seleccionada;
- sin comunicacion con motores.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

import cv2
from PIL import Image, ImageTk


APP_TITLE = "REFLEKTOR"
MAX_CAMERA_INDICES = 10
PREVIEW_WIDTH = 960
PREVIEW_HEIGHT = 540
BG = "#101010"
TEXT = "#e8e8e8"
MUTED = "#9a9a9a"
ERROR = "#ff5c7a"
BLACK_FRAME_THRESHOLD = 2.0
WARMUP_FRAMES = 20


@dataclass(frozen=True)
class BackendOption:
    label: str
    api_preference: int | None


def build_backend_options() -> list[BackendOption]:
    if sys.platform.startswith("win"):
        return [
            BackendOption("DirectShow (recomendado)", cv2.CAP_DSHOW),
            BackendOption("MSMF / Windows Media", cv2.CAP_MSMF),
            BackendOption("OpenCV default", None),
        ]

    return [BackendOption("OpenCV default", None)]


@dataclass(frozen=True)
class CameraOption:
    index: int
    name: str

    @property
    def label(self) -> str:
        return f"{self.index} — {self.name}"


def get_windows_camera_names() -> list[str]:
    """Best-effort camera names from Windows device manager."""
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
            "$_.Name -match 'Camera|Camara|Cámara|Webcam|Video' "
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


def build_camera_options(max_indices: int = MAX_CAMERA_INDICES) -> list[CameraOption]:
    names = get_windows_camera_names()
    options: list[CameraOption] = []

    for index in range(max(1, max_indices)):
        name = names[index] if index < len(names) else f"Camara OpenCV {index}"
        options.append(CameraOption(index=index, name=name))

    return options


def open_camera(index: int, backend: BackendOption) -> cv2.VideoCapture:
    if backend.api_preference is None:
        cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index, backend.api_preference)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, PREVIEW_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PREVIEW_HEIGHT)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


def read_warm_frame(capture: cv2.VideoCapture, attempts: int = WARMUP_FRAMES):
    last_frame = None
    last_ok = False

    for _ in range(attempts):
        last_ok, frame = capture.read()
        if last_ok and frame is not None:
            last_frame = frame
            if float(frame.mean()) > BLACK_FRAME_THRESHOLD:
                return True, frame

    return last_ok and last_frame is not None, last_frame


class CameraSelectorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("980x620")
        self.root.minsize(780, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.camera_options = build_camera_options()
        self.backend_options = build_backend_options()
        self.camera_by_label = {option.label: option for option in self.camera_options}
        self.backend_by_label = {option.label: option for option in self.backend_options}
        self.selected_camera = tk.StringVar(value=self.camera_options[0].label)
        self.selected_backend = tk.StringVar(value=self.backend_options[0].label)
        self.status = tk.StringVar(value="Selecciona una camara y pulsa Abrir camara.")

        self.capture: cv2.VideoCapture | None = None
        self.running = False
        self.photo: ImageTk.PhotoImage | None = None
        self.canvas_image_id: int | None = None

        self.configure_style()
        self.build_ui()
        self.draw_placeholder("Preview de camara")

    def configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure(
            "TButton",
            background="#242424",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(10, 5),
            font=("Segoe UI", 9),
        )
        style.map("TButton", background=[("active", "#303030"), ("disabled", "#1a1a1a")])
        style.configure(
            "TCombobox",
            fieldbackground="#181818",
            background="#181818",
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor="#333333",
            lightcolor="#333333",
            darkcolor="#333333",
            padding=4,
        )

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 8))

        self.combo = ttk.Combobox(
            controls,
            textvariable=self.selected_camera,
            values=[option.label for option in self.camera_options],
            state="readonly",
            width=42,
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.backend_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_backend,
            values=[option.label for option in self.backend_options],
            state="readonly",
            width=22,
        )
        self.backend_combo.pack(side=tk.LEFT, padx=(0, 6))

        self.open_button = ttk.Button(controls, text="abrir", command=self.start_camera)
        self.open_button.pack(side=tk.LEFT, padx=(0, 4))

        self.stop_button = ttk.Button(controls, text="cerrar", command=self.stop_camera, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(
            outer,
            width=PREVIEW_WIDTH,
            height=PREVIEW_HEIGHT,
            bg=BG,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.status_label = ttk.Label(outer, textvariable=self.status, style="Muted.TLabel")
        self.status_label.pack(anchor=tk.W)

    def selected_index(self) -> int:
        return self.camera_by_label[self.selected_camera.get()].index

    def selected_backend_option(self) -> BackendOption:
        return self.backend_by_label[self.selected_backend.get()]

    def start_camera(self) -> None:
        self.stop_camera()

        index = self.selected_index()
        backend = self.selected_backend_option()
        self.status.set(f"Abriendo camara {index} con {backend.label}...")
        self.root.update_idletasks()

        capture = open_camera(index, backend)
        if not capture.isOpened():
            capture.release()
            self.status.set(f"No se pudo abrir la camara {index} con {backend.label}.")
            self.draw_placeholder(f"No se pudo abrir camara {index}", color=ERROR)
            return

        ok, frame = read_warm_frame(capture)
        if not ok or frame is None:
            capture.release()
            self.status.set(f"La camara {index} abre, pero no entrega imagen.")
            self.draw_placeholder(f"Camara {index} sin imagen", color=ERROR)
            return

        self.capture = capture
        self.running = True
        self.open_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.combo.configure(state=tk.DISABLED)
        self.backend_combo.configure(state=tk.DISABLED)
        mean = float(frame.mean())
        if mean <= BLACK_FRAME_THRESHOLD:
            self.status.set(
                f"Camara activa, pero imagen negra. Prueba otro backend. Brillo medio: {mean:.1f}"
            )
        else:
            self.status.set(f"Camara activa: {self.selected_camera.get()} | {backend.label}")
        self.show_frame(frame)
        self.update_preview()

    def stop_camera(self) -> None:
        self.running = False
        if self.capture is not None:
            self.capture.release()
            self.capture = None

        self.open_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.combo.configure(state="readonly")
        self.backend_combo.configure(state="readonly")

    def update_preview(self) -> None:
        if not self.running or self.capture is None:
            return

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.status.set("No se pudo leer frame de la camara.")
            self.draw_placeholder("Sin frame de camara", color=ERROR)
            self.root.after(250, self.update_preview)
            return

        mean = float(frame.mean())
        if mean <= BLACK_FRAME_THRESHOLD:
            self.status.set(
                f"Camara activa, pero imagen negra. Backend: {self.selected_backend.get()} | brillo: {mean:.1f}"
            )
        else:
            self.status.set(
                f"Camara activa: {self.selected_camera.get()} | {self.selected_backend.get()} | brillo: {mean:.1f}"
            )
        self.show_frame(frame)
        self.root.after(15, self.update_preview)

    def show_frame(self, frame) -> None:
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image=image)

        x = canvas_width // 2
        y = canvas_height // 2
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        else:
            self.canvas.itemconfigure(self.canvas_image_id, image=self.photo)
            self.canvas.coords(self.canvas_image_id, x, y)

    def draw_placeholder(self, text: str, color: str = MUTED) -> None:
        self.canvas.delete("all")
        self.canvas_image_id = None
        width = max(1, self.canvas.winfo_width() or PREVIEW_WIDTH)
        height = max(1, self.canvas.winfo_height() or PREVIEW_HEIGHT)
        self.canvas.create_rectangle(0, 0, width, height, fill=BG, outline="")
        self.canvas.create_text(
            width // 2,
            height // 2,
            text=text,
            fill=color,
            font=("Segoe UI", 12),
        )

    def close(self) -> None:
        self.stop_camera()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    CameraSelectorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
