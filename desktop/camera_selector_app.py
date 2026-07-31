from __future__ import annotations

import tkinter as tk

import cv2
from PIL import Image, ImageTk


CAMERA_INDEX = 2
WINDOW_TITLE = "REFLEKTOR"
BG = "#101010"
ERROR = "#ff5c7a"


def open_camera() -> cv2.VideoCapture:
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("980x620")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.cap: cv2.VideoCapture | None = open_camera()
        self.photo: ImageTk.PhotoImage | None = None
        self.image_id: int | None = None

        if self.cap is None or not self.cap.isOpened():
            self.error("no se pudo abrir la camara")
            return

        self.update()

    def update(self) -> None:
        if self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.error("sin imagen")
            self.root.after(250, self.update)
            return

        self.show(frame)
        self.root.after(15, self.update)

    def show(self, frame) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
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
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
