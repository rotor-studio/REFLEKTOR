"""
REFLEKTOR - camara simple

App minima:
- desplegable de camara;
- boton "seleccionar camara";
- preview de video.

Sin escaner, sin backend visible, sin logica de motores.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

import cv2
from PIL import Image, ImageTk


BG = "#101010"
TEXT = "#e8e8e8"
MUTED = "#9a9a9a"
ERROR = "#ff5c7a"
PREVIEW_WIDTH = 960
PREVIEW_HEIGHT = 540


@dataclass(frozen=True)
class CameraOption:
    index: int
    name: str

    @property
    def label(self) -> str:
        return f"{self.index} - {self.name}"


CAMERAS = [
    CameraOption(0, "Camara 0"),
    CameraOption(1, "Camara 1"),
    CameraOption(2, "Microsoft LifeCam Studio"),
    CameraOption(3, "Camara 3"),
]


def open_camera(index: int) -> cv2.VideoCapture:
    # DirectShow evita el error cap_msmf en Windows.
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("REFLEKTOR")
        self.root.configure(bg=BG)
        self.root.geometry("980x620")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.camera_by_label = {camera.label: camera for camera in CAMERAS}
        self.selected_camera = tk.StringVar(value=CAMERAS[2].label)
        self.status = tk.StringVar(value="selecciona camara")

        self.cap: cv2.VideoCapture | None = None
        self.running = False
        self.photo: ImageTk.PhotoImage | None = None
        self.image_id: int | None = None

        self.configure_style()
        self.build_ui()
        self.placeholder("sin camara")

    def configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
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
        style.configure(
            "TButton",
            background="#242424",
            foreground=TEXT,
            borderwidth=0,
            padding=(10, 5),
            font=("Segoe UI", 9),
        )
        style.map("TButton", background=[("active", "#303030"), ("disabled", "#1a1a1a")])

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 8))

        self.combo = ttk.Combobox(
            controls,
            textvariable=self.selected_camera,
            values=[camera.label for camera in CAMERAS],
            state="readonly",
            width=38,
        )
        self.combo.pack(side=tk.LEFT, padx=(0, 6))

        self.button = ttk.Button(controls, text="seleccionar camara", command=self.select_camera)
        self.button.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        ttk.Label(outer, textvariable=self.status).pack(anchor=tk.W)

    def selected_index(self) -> int:
        return self.camera_by_label[self.selected_camera.get()].index

    def select_camera(self) -> None:
        self.stop()

        index = self.selected_index()
        self.status.set(f"abriendo camara {index}")
        self.root.update_idletasks()

        cap = open_camera(index)
        if not cap.isOpened():
            cap.release()
            self.status.set(f"no se pudo abrir camara {index}")
            self.placeholder("no abre", ERROR)
            return

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            self.status.set(f"camara {index} sin imagen")
            self.placeholder("sin imagen", ERROR)
            return

        self.cap = cap
        self.running = True
        self.status.set(f"camara activa: {self.selected_camera.get()}")
        self.show_frame(frame)
        self.update()

    def update(self) -> None:
        if not self.running or self.cap is None:
            return

        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.show_frame(frame)
            self.status.set(f"camara activa: {self.selected_camera.get()} | brillo {frame.mean():.1f}")
        else:
            self.status.set("sin frame")

        self.root.after(15, self.update)

    def show_frame(self, frame) -> None:
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image=image)

        x = canvas_width // 2
        y = canvas_height // 2
        if self.image_id is None:
            self.image_id = self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        else:
            self.canvas.itemconfigure(self.image_id, image=self.photo)
            self.canvas.coords(self.image_id, x, y)

    def placeholder(self, text: str, color: str = MUTED) -> None:
        self.canvas.delete("all")
        self.image_id = None
        self.canvas.create_text(
            max(1, self.canvas.winfo_width()) // 2,
            max(1, self.canvas.winfo_height()) // 2,
            text=text,
            fill=color,
            font=("Segoe UI", 12),
        )

    def stop(self) -> None:
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def close(self) -> None:
        self.stop()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
