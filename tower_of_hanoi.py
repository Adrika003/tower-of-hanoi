import math
import os
import random
import threading
import tkinter as tk

try:
    import winsound
except ImportError:
    winsound = None

CANVAS_W, CANVAS_H = 900, 480
BASE_Y = 410
PEG_H = 240
PEG_W = 16
PEG_X = [160, 450, 740]
DISK_H = 34
MAX_DISK_W = 230
MIN_DISK_W = 80
DRAG_THRESHOLD = 8

BG = "#FFF0F6"
TITLE_FG = "#E75699"
MOVE_FG = "#9B5DE5"
HINT_FG = "#B07CC6"
ERROR_FG = "#FF6B8A"
BTN_BG = "#FF9ED2"
BTN_ACTIVE = "#FF7BC1"
BTN_FG = "#6B2D5B"
PEG_COLOR = "#C9A7EB"
PEG_OUTLINE = "#A67BD4"
BOARD_COLOR = "#E5C3FF"
BOARD_OUTLINE = "#C9A0DC"
HIGHLIGHT = "#FFF4B8"

CANDY_COLORS = [
    "#FFB5E8", "#FFC9DE", "#FDD5B1", "#FFF1A8",
    "#C7F9CC", "#B0E0FF", "#D5C6FF", "#F5B7FF",
]
SPRINKLE_COLORS = [
    "#FF9ED2", "#B0E0FF", "#FFF1A8", "#C7F9CC",
    "#D5C6FF", "#FFC9DE", "#FDD5B1",
]

FONT_TITLE = ("Comic Sans MS", 24, "bold")
FONT_UI = ("Comic Sans MS", 12, "bold")
FONT_HINT = ("Comic Sans MS", 11)
FONT_PEG = ("Comic Sans MS", 14, "bold")


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1 + r, x2, y2 - r,
        x2 - r, y2, x1 + r, y2, x1, y2 - r, x1, y1 + r,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


class TowerOfHanoi:
    def __init__(self, root):
        self.root = root
        self.root.title("Tower of Hanoi - Candy Land")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.n = 4
        self.pegs = [[], [], []]
        self.moves = 0
        self.selected = None
        self.won = False
        self.sprinkles = []
        self._pending = None
        self._press_xy = (0, 0)
        self._dragging = False
        self._drag_src = None
        self._drag_item = None
        self._drag_grab = (0, 0)
        self._disk_items = [[], [], []]
        self._hint_after = None
        self._confetti = []

        self._build_header()
        self._build_canvas()
        self._build_footer()
        self.root.bind("<Escape>", lambda e: self._clear_selection())

        self._set_window_icon()

        self.new_game(4)

    def _set_window_icon(self):
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "girl.png"
        )
        if not os.path.exists(path):
            return
        try:
            img = tk.PhotoImage(file=path)
            scale = max(1, int(math.ceil(max(img.width(), img.height()) / 64)))
            if scale > 1:
                img = img.subsample(scale, scale)
            self.root.iconphoto(True, img)
            self._icon_photo = img
        except tk.TclError:
            pass

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(
            header, text="Tower of Hanoi", font=FONT_TITLE,
            fg=TITLE_FG, bg=BG,
        ).pack(side="left")

        right = tk.Frame(header, bg=BG)
        right.pack(side="right")

        tk.Label(right, text="Disks:", font=FONT_UI, fg=HINT_FG, bg=BG).pack(
            side="left", padx=(0, 6)
        )
        self.diff_var = tk.StringVar(value="4")
        self.diff_menu = tk.OptionMenu(
            right, self.diff_var, "3", "4", "5", "6", "7", "8",
            command=self._on_diff_change,
        )
        self.diff_menu.config(
            font=FONT_UI, bg="#FFFFFF", fg=BTN_FG, activebackground=BTN_ACTIVE,
            activeforeground=BTN_FG, highlightthickness=1,
            highlightbackground=BTN_BG, relief="flat", width=3, padx=8,
        )
        self.diff_menu["menu"].config(
            font=FONT_UI, bg="#FFFFFF", fg=BTN_FG, activebackground=BTN_BG
        )
        self.diff_menu.pack(side="left", padx=(0, 14))

        self.moves_var = tk.StringVar(value="Moves: 0   Best: 15")
        tk.Label(
            right, textvariable=self.moves_var, font=FONT_UI, fg=MOVE_FG, bg=BG
        ).pack(side="left", padx=(0, 14))

        self.new_btn = tk.Button(
            right, text="New Game", font=FONT_UI, bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE, activeforeground=BTN_FG,
            relief="flat", padx=14, pady=4, cursor="hand2",
            command=lambda: self.new_game(int(self.diff_var.get())),
        )
        self.new_btn.pack(side="left")

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self.root, width=CANVAS_W, height=CANVAS_H,
            bg=BG, highlightthickness=0,
        )
        self.canvas.pack(padx=16, pady=6)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def _build_footer(self):
        self.hint_var = tk.StringVar()
        self.hint_label = tk.Label(
            self.root, textvariable=self.hint_var, font=FONT_HINT,
            fg=HINT_FG, bg=BG,
        )
        self.hint_label.pack(pady=(0, 12))

    def _set_hint(self, text, color=HINT_FG, revert=True):
        if self._hint_after is not None:
            self.root.after_cancel(self._hint_after)
            self._hint_after = None
        self.hint_var.set(text)
        self.hint_label.configure(fg=color)
        if revert and text != self._default_hint():
            self._hint_after = self.root.after(
                2200, lambda: self._set_hint(self._default_hint(), HINT_FG, revert=False)
            )

    def _default_hint(self):
        return (
            "Drag a disk (or click it, then click a peg) — "
            "move every disk to the right peg!  ✿"
        )

    def _on_diff_change(self, value):
        self.new_game(int(value))

    def new_game(self, n=None):
        if n is None:
            n = int(self.diff_var.get())
        self.n = n
        self.diff_var.set(str(n))
        self.pegs = [list(range(n, 0, -1)), [], []]
        self.moves = 0
        self.selected = None
        self.won = False
        self._pending = None
        self._dragging = False
        self._drag_src = None
        self._drag_item = None
        for item in self._confetti:
            self.canvas.delete(item)
        self._confetti = []
        self.sprinkles = []
        for _ in range(48):
            self.sprinkles.append((
                random.randint(10, CANVAS_W - 10),
                random.randint(10, CANVAS_H - 90),
                random.choice(SPRINKLE_COLORS),
                random.randint(-30, 30),
            ))
        self._update_moves_label()
        self._set_hint(self._default_hint(), HINT_FG, revert=False)
        self.redraw()

    def _update_moves_label(self):
        best = (1 << self.n) - 1
        self.moves_var.set(f"Moves: {self.moves}   Best: {best}")

    def disk_width(self, size):
        if self.n <= 1:
            return MAX_DISK_W
        return MIN_DISK_W + (size - 1) * (MAX_DISK_W - MIN_DISK_W) / (self.n - 1)

    def peg_at(self, x):
        if x is None or x < 0 or x > CANVAS_W:
            return None
        if x < 300:
            return 0
        if x < 600:
            return 1
        return 2

    def redraw(self):
        c = self.canvas
        c.delete("all")
        self._disk_items = [[], [], []]

        c.create_rectangle(0, 0, CANVAS_W, CANVAS_H, fill=BG, outline="")

        for x, y, color, ang in self.sprinkles:
            rad = ang * 3.14159 / 180
            dx = 7 * math.cos(rad)
            dy = 7 * math.sin(rad)
            c.create_line(
                x, y, x + dx, y + dy, fill=color, width=3,
                capstyle="round",
            )

        if self.selected is not None:
            px = PEG_X[self.selected]
            rounded_rect(
                c, px - 95, BASE_Y - PEG_H - 30, px + 95, BASE_Y + 8,
                24, fill=HIGHLIGHT, outline="",
            )

        rounded_rect(
            c, 40, BASE_Y, 860, BASE_Y + 40, 18,
            fill=BOARD_COLOR, outline=BOARD_OUTLINE, width=3,
        )

        for i, px in enumerate(PEG_X):
            rounded_rect(
                c, px - PEG_W // 2, BASE_Y - PEG_H,
                px + PEG_W // 2, BASE_Y + 4, 7,
                fill=PEG_COLOR, outline=PEG_OUTLINE, width=2,
            )
            c.create_text(
                px, BASE_Y + 62, text="ABC"[i], font=FONT_PEG,
                fill=MOVE_FG,
            )

        for p in range(3):
            stack = self.pegs[p]
            for i, size in enumerate(stack):
                if (
                    self._dragging
                    and p == self._drag_src
                    and i == len(stack) - 1
                ):
                    self._disk_items[p].append(None)
                    continue
                lift = 24 if (self.selected == p and i == len(stack) - 1) else 0
                item = self._draw_disk(p, i, size, lift)
                self._disk_items[p].append(item)

        if self.selected is not None:
            c.create_text(
                PEG_X[self.selected], BASE_Y - PEG_H - 48,
                text="picked up!", font=FONT_HINT, fill=TITLE_FG,
            )

    def _draw_disk(self, peg, index, size, lift=0):
        w = self.disk_width(size)
        x = PEG_X[peg]
        y_bottom = BASE_Y - index * DISK_H - lift
        x1, y1 = x - w / 2, y_bottom - DISK_H
        x2, y2 = x + w / 2, y_bottom
        color = CANDY_COLORS[(size - 1) % len(CANDY_COLORS)]
        item = rounded_rect(
            self.canvas, x1, y1, x2, y2, DISK_H / 2 - 2,
            fill=color, outline="#FFFFFF", width=2,
        )
        self.canvas.create_text(
            x, (y1 + y2) / 2, text=str(size), font=FONT_UI,
            fill="#8A4F7D",
        )
        return item

    def on_press(self, event):
        if self.won:
            return
        peg = self.peg_at(event.x)
        self._press_xy = (event.x, event.y)
        self._dragging = False

        if self.selected is not None:
            self._pending = ("move", peg)
            return

        if peg is None or not self.pegs[peg]:
            self._pending = None
            return
        self._pending = ("drag", peg)
        self._drag_src = peg

    def on_motion(self, event):
        if self.won or self._dragging:
            if self._dragging and self._drag_item is not None:
                coords = self.canvas.coords(self._drag_item)
                w = coords[2] - coords[0]
                h = coords[3] - coords[1]
                nx = event.x - self._drag_grab[0]
                ny = event.y - self._drag_grab[1]
                self.canvas.coords(self._drag_item, nx, ny, nx + w, ny + h)
            return

        if not self._pending or self._pending[0] != "drag":
            return

        dx = event.x - self._press_xy[0]
        dy = event.y - self._press_xy[1]
        if abs(dx) < DRAG_THRESHOLD and abs(dy) < DRAG_THRESHOLD:
            return

        src = self._drag_src
        if not self.pegs[src]:
            self._pending = None
            return

        self._dragging = True
        stack = self.pegs[src]
        item = self._disk_items[src][-1]
        if item is None:
            self._dragging = False
            self._pending = None
            return
        coords = self.canvas.coords(item)
        self._drag_grab = (
            event.x - coords[0],
            event.y - coords[1],
        )
        self._drag_item = item
        self.canvas.tag_raise(item)
        self._play_tone(700, 40)

    def on_release(self, event):
        if self.won:
            self._pending = None
            self._dragging = False
            return

        pending, self._pending = self._pending, None

        if self._dragging:
            src = self._drag_src
            target = self.peg_at(event.x)
            self._dragging = False
            self._drag_item = None
            self._drag_src = None
            if target is None:
                self.redraw()
            else:
                self.try_move(src, target)
            return

        if pending is None:
            return

        kind, peg = pending

        if kind == "move":
            target = self.peg_at(event.x)
            if target is None:
                return
            if target == self.selected:
                self._clear_selection()
                return
            src = self.selected
            self.selected = None
            self.try_move(src, target)
            return

        if kind == "drag":
            clicked = self.peg_at(event.x)
            if clicked is not None and self.pegs[clicked]:
                self.selected = clicked
                self._play_tone(880, 50)
                self._set_hint(
                    "Now click the peg where you want to drop it!",
                    TITLE_FG, revert=False,
                )
                self.redraw()

    def _clear_selection(self):
        if self.selected is not None:
            self.selected = None
            self._set_hint(self._default_hint(), HINT_FG, revert=False)
            self.redraw()

    def try_move(self, src, dst):
        if src is None or dst is None or src == dst:
            return False
        if not self.pegs[src]:
            self._play_tone(220, 120)
            self._set_hint("That peg has no disks!", ERROR_FG)
            self.redraw()
            return False

        moving = self.pegs[src][-1]
        if self.pegs[dst] and self.pegs[dst][-1] < moving:
            self._play_tone(200, 160)
            self._set_hint(
                "Oops! A bigger disk can't go on a smaller one. ✗",
                ERROR_FG,
            )
            self.redraw()
            return False

        self.pegs[src].pop()
        self.pegs[dst].append(moving)
        self.moves += 1
        self._update_moves_label()
        self._play_tone(620, 60)
        self.redraw()

        if len(self.pegs[2]) == self.n:
            self.won = True
            self._set_hint(
                "You did it! 🍬", TITLE_FG, revert=False,
            )
            self.root.after(250, self._celebrate)
        return True

    def _celebrate(self):
        self._start_confetti()
        self._play_win_sound()
        self._show_win_dialog()

    def _start_confetti(self):
        self._confetti = []
        for _ in range(100):
            x = random.randint(0, CANVAS_W)
            y = random.randint(-140, -10)
            w = random.randint(6, 12)
            h = random.randint(8, 16)
            color = random.choice(CANDY_COLORS)
            item = self.canvas.create_rectangle(
                x, y, x + w, y + h, fill=color, outline=""
            )
            self._confetti.append(item)
        self._confetti_v = [
            (item, random.uniform(-2.5, 2.5), random.uniform(4, 8))
            for item in self._confetti
        ]
        self._confetti_alive = True
        self.root.after(40, self._animate_confetti)

    def _animate_confetti(self):
        if not getattr(self, "_confetti_alive", False):
            return
        alive = False
        for entry in list(self._confetti_v):
            item, dx, dy = entry
            self.canvas.move(item, dx, dy)
            coords = self.canvas.coords(item)
            if coords and coords[1] < CANVAS_H + 20:
                alive = True
            else:
                try:
                    self._confetti_v.remove(entry)
                except ValueError:
                    pass
        if alive:
            self.root.after(40, self._animate_confetti)
        else:
            self._confetti_alive = False

    def _show_win_dialog(self):
        best = (1 << self.n) - 1
        dlg = tk.Toplevel(self.root)
        dlg.title("You Win!")
        dlg.configure(bg="#FFE3F1")
        dlg.resizable(False, False)
        dlg.transient(self.root)

        frame = tk.Frame(dlg, bg="#FFE3F1", padx=30, pady=22)
        frame.pack()

        tk.Label(
            frame, text="You did it!  🍭",
            font=("Comic Sans MS", 22, "bold"), fg=TITLE_FG, bg="#FFE3F1",
        ).pack(pady=(0, 8))
        tk.Label(
            frame,
            text=f"You finished in {self.moves} moves!",
            font=FONT_UI, fg=BTN_FG, bg="#FFE3F1",
        ).pack()
        if self.moves == best:
            msg = "Perfect! That's the optimal solution!"
            color = "#2DBE7E"
        else:
            msg = f"Optimal is {best} moves — try again for perfect!"
            color = MOVE_FG
        tk.Label(
            frame, text=msg, font=FONT_HINT, fg=color, bg="#FFE3F1",
        ).pack(pady=(4, 16))

        btns = tk.Frame(frame, bg="#FFE3F1")
        btns.pack()

        def again():
            dlg.destroy()
            self.new_game(int(self.diff_var.get()))

        def close():
            dlg.destroy()

        tk.Button(
            btns, text="Play Again", font=FONT_UI, bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE, relief="flat", padx=16, pady=6,
            cursor="hand2", command=again,
        ).pack(side="left", padx=(0, 10))
        tk.Button(
            btns, text="Close", font=FONT_UI, bg="#FFFFFF", fg=BTN_FG,
            activebackground=BTN_BG, relief="flat", padx=16, pady=6,
            cursor="hand2", command=close,
        ).pack(side="left")

        dlg.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(px, 0)}+{max(py, 0)}")
        dlg.grab_set()

    def _play_tone(self, freq, dur):
        if winsound is None:
            return

        def beep():
            try:
                winsound.Beep(freq, dur)
            except Exception:
                pass

        threading.Thread(target=beep, daemon=True).start()

    def _play_win_sound(self):
        if winsound is None:
            return
        notes = [
            (523, 120), (659, 120), (784, 120),
            (1046, 220), (784, 100), (1046, 350),
        ]

        def melody():
            for freq, dur in notes:
                try:
                    winsound.Beep(freq, dur)
                except Exception:
                    return

        threading.Thread(target=melody, daemon=True).start()


def _hide_console():
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _set_app_user_model_id():
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "TowerOfHanoi.CandyLand.1"
        )
    except Exception:
        pass


def main():
    _hide_console()
    _set_app_user_model_id()
    root = tk.Tk()
    app = TowerOfHanoi(root)
    root.mainloop()


if __name__ == "__main__":
    main()
