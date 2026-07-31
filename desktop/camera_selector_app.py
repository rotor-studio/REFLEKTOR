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


APP_TITLE = "REFLEKTOR - Camera Selector"
MAX_CAMERA_INDICES = 10
PREVIEW_WIDTH = 960
PREVIEW_HEIGHT = 540
BG = "#101114"
PANEL = "#181a20"
TEXT = "#f2f2f2"
MUTED = "#9aa0aa"
ACCENT = "#7c5cff"
ERROR = "#ff5c7a"


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


def open_camera(index: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, PREVIEW_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PREVIEW_HEIGHT)
    return cap


class CameraSelectorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.camera_options = build_camera_options()
        self.camera_by_label = {option.label: option for option in self.camera_options}
        self.selected_camera = tk.StringVar(value=self.camera_options[0].label)
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
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure(
            "TButton",
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("TButton", background=[("active", "#9178ff"), ("disabled", "#3a3d46")])
        style.configure(
            "TCombobox",
            fieldbackground="#222530",
            background="#222530",
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor="#2f3340",
            lightcolor="#2f3340",
            darkcolor="#2f3340",
            padding=6,
        )

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 14))

        title_block = ttk.Frame(header)
        title_block.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title = tk.Label(
            title_block,
            text="REFLEKTOR",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 22, "bold"),
        )
        title.pack(anchor=tk.W)

        subtitle = ttk.Label(
            title_block,
            text="Selector de camara para la nueva app de motores",
            style="Muted.TLabel",
        )
        subtitle.pack(anchor=tk.W)

        controls = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        controls.pack(fill=tk.X, pady=(0, 14))

        ttk.Label(controls, text="Camara", background=PANEL).pack(side=tk.LEFT, padx=(0, 10))

        self.combo = ttk.Combobox(
            controls,
            textvariable=self.selected_camera,
            values=[option.label for option in self.camera_options],
            state="readonly",
            width=58,
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        self.open_button = ttk.Button(controls, text="Abrir camara", command=self.start_camera)
        self.open_button.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_button = ttk.Button(controls, text="Cerrar", command=self.stop_camera, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        preview_panel = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        preview_panel.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            preview_panel,
            width=PREVIEW_WIDTH,
            height=PREVIEW_HEIGHT,
            bg="#050608",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        status_bar = ttk.Frame(outer)
        status_bar.pack(fill=tk.X, pady=(12, 0))
        self.status_label = ttk.Label(status_bar, textvariable=self.status, style="Muted.TLabel")
        self.status_label.pack(anchor=tk.W)

    def selected_index(self) -> int:
        return self.camera_by_label[self.selected_camera.get()].index

    def start_camera(self) -> None:
        self.stop_camera()

        index = self.selected_index()
        self.status.set(f"Abriendo camara {index}...")
        self.root.update_idletasks()

        capture = open_camera(index)
        if not capture.isOpened():
            capture.release()
            self.status.set(f"No se pudo abrir la camara {index}. Prueba otro indice.")
            self.draw_placeholder(f"No se pudo abrir camara {index}", color=ERROR)
            return

        ok, frame = capture.read()
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
        self.status.set(f"Camara activa: {self.selected_camera.get()}")
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
        self.status.set(f"Camara activa: {self.selected_camera.get()} | brillo medio: {mean:.1f}")
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
        self.canvas.create_rectangle(0, 0, width, height, fill="#050608", outline="")
        self.canvas.create_text(
            width // 2,
            height // 2,
            text=text,
            fill=color,
            font=("Segoe UI", 24, "bold"),
        )
        self.canvas.create_text(
            width // 2,
            height // 2 + 42,
            text="El siguiente paso sera conectar esta seleccion con la logica de motores.",
            fill=MUTED,
            font=("Segoe UI", 11),
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

