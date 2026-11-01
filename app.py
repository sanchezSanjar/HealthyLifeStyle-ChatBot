"""HealthyCoach desktop app: health profile dashboard + streaming chat (Tkinter)."""
from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "healthycoach.log"

# Without a console (HealthyCoach.exe uses pythonw) stdout/stderr are None; log instead.
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(LOG_FILE, "w", encoding="utf-8", buffering=1)

try:
    from healthbot.chat import Coach
    from healthbot.profile import ACTIVITY_FACTORS, Profile, load_profile, save_profile
except Exception:
    traceback.print_exc()
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror("HealthyCoach could not start",
                         "Python packages are missing. Run INSTALL_WINDOWS.bat, then try again.")
    sys.exit(1)

BG = "#f3f6f1"
CARD = "#ffffff"
LINE = "#e2e8df"
GREEN = "#2f9e6e"
GREEN_DARK = "#237a55"
GREEN_SOFT = "#e3f4ea"
ORANGE = "#f2a541"
BLUE = "#5b9bd5"
RED = "#e06c5f"
TEXT = "#1f2d27"
MUTED = "#6b7c74"
FONT = "Segoe UI"

ACTIVITY_LABELS = {
    "sedentary": "Sedentary (little exercise)",
    "light": "Light (1-3 days/week)",
    "moderate": "Moderate (3-5 days/week)",
    "active": "Active (6-7 days/week)",
    "very_active": "Very active (hard training)",
}
TOPICS = {
    "Nutrition": ("#2f9e6e", ["Plan a healthy breakfast for me", "What are good high-protein snacks?",
                              "How can I eat more vegetables every day?"]),
    "Fitness": ("#f2a541", ["Give me a 20-minute home workout", "How often should I exercise each week?",
                            "How do I start running as a beginner?"]),
    "Sleep": ("#7b6fd6", ["How can I fall asleep faster?", "How many hours of sleep do adults need?",
                          "What should I avoid before bedtime?"]),
    "Stress": ("#e06c5f", ["Give me a quick breathing exercise for stress", "How can I manage stress at work?",
                           "What are simple mindfulness habits?"]),
    "Hydration": ("#5b9bd5", ["Why is drinking water important?", "How can I remember to drink more water?",
                              "What are signs of dehydration?"]),
}


class HealthyCoachApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("HealthyCoach — Healthy Lifestyle ChatBot")
        root.geometry("1240x800")
        root.minsize(1000, 640)
        root.configure(bg=BG)
        icon = ROOT / "assets" / "healthycoach.ico"
        if icon.exists():
            root.iconbitmap(default=str(icon))

        self.coach: Coach | None = None
        self.profile = load_profile()
        self.use_profile = tk.BooleanVar(value=True)
        self.events: queue.Queue = queue.Queue()  # worker threads -> Tk thread
        self.stop_event = threading.Event()
        self.busy = False
        self.bubbles: list[tk.Label] = []
        self.wrap = 520
        self.answer_label = None
        self.answer_meta = None
        self.started_at = 0.0

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Feed.Vertical.TScrollbar", background=LINE, troughcolor=BG, bordercolor=BG,
                        lightcolor=LINE, darkcolor=LINE, arrowcolor=MUTED, gripcount=0)
        style.configure("Form.TCombobox", fieldbackground=CARD, background=CARD, bordercolor=LINE,
                        arrowcolor=GREEN, padding=6)

        self._build_header()
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        self.side = tk.Frame(body, bg=BG, width=330)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        self._build_chat(body)
        self._render_side()
        self._select_topic("Nutrition")
        self._welcome()

        root.after(200, self._start_loading)
        root.after(50, self._drain_events)

    # ---------------------------------------------------------------- header
    def _build_header(self):
        bar = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        bar.pack(fill="x")
        logo = tk.Canvas(bar, width=44, height=44, bg=BG, highlightthickness=0)
        logo.create_oval(2, 2, 42, 42, fill=GREEN, outline="")
        logo.create_polygon(22, 10, 33, 22, 22, 35, 11, 22, fill="#ffffff", smooth=True, outline="")
        logo.create_line(22, 14, 22, 33, fill=GREEN, width=2)
        logo.pack(side="left")
        names = tk.Frame(bar, bg=BG)
        names.pack(side="left", padx=12)
        tk.Label(names, text="HealthyCoach", bg=BG, fg=TEXT, font=(FONT, 17, "bold")).pack(anchor="w")
        tk.Label(names, text="Your private healthy-lifestyle chatbot", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")

        self.status = tk.Label(bar, text="  Loading model…  ", bg="#fff3dd", fg="#9a6a12",
                               font=(FONT, 9, "bold"), padx=10, pady=5)
        self.status.pack(side="right")
        self.device = tk.Label(bar, text="", bg=BG, fg=MUTED, font=(FONT, 9))
        self.device.pack(side="right", padx=12)

    def _set_status(self, text, kind="wait"):
        colors = {"wait": ("#fff3dd", "#9a6a12"), "ok": (GREEN_SOFT, GREEN_DARK), "bad": ("#fde4e1", "#a53a2f")}
        bg, fg = colors[kind]
        self.status.configure(text=f"  {text}  ", bg=bg, fg=fg)

    # ------------------------------------------------------------ side panel
    def _card(self, parent, title=None):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE, padx=18, pady=16)
        card.pack(fill="x", pady=(0, 14))
        if title:
            tk.Label(card, text=title, bg=CARD, fg=TEXT, font=(FONT, 12, "bold")).pack(anchor="w", pady=(0, 10))
        return card

    def _render_side(self):
        for child in self.side.winfo_children():
            child.destroy()
        if self.profile is None:
            self._profile_form()
        else:
            self._profile_summary()

    def _profile_form(self):
        current = self.profile or Profile()
        card = self._card(self.side, "My health profile")
        tk.Label(card, text="Used to calculate your targets and personalise answers.\nSaved only on this PC.",
                 bg=CARD, fg=MUTED, font=(FONT, 8), justify="left").pack(anchor="w", pady=(0, 10))

        self.f_name = tk.StringVar(value=current.name)
        self.f_age = tk.StringVar(value=str(current.age))
        self.f_height = tk.StringVar(value=f"{current.height_cm:g}")
        self.f_weight = tk.StringVar(value=f"{current.weight_kg:g}")
        self.f_sex = tk.StringVar(value=current.sex)
        self.f_goal = tk.StringVar(value=current.goal)
        self.f_activity = tk.StringVar(value=ACTIVITY_LABELS[current.activity])

        self._entry(card, "Name (optional)", self.f_name)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x")
        row.columnconfigure((0, 1, 2), weight=1, uniform="field")
        for column, (label, var) in enumerate((("Age", self.f_age), ("Height cm", self.f_height),
                                               ("Weight kg", self.f_weight))):
            cell = tk.Frame(row, bg=CARD)
            cell.grid(row=0, column=column, sticky="ew", padx=(0, 6 if column < 2 else 0))
            self._entry(cell, label, var)
        self._segmented(card, "Sex", self.f_sex, [("male", "Male"), ("female", "Female")])
        tk.Label(card, text="Activity", bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", pady=(4, 2))
        ttk.Combobox(card, textvariable=self.f_activity, values=list(ACTIVITY_LABELS.values()),
                     state="readonly", style="Form.TCombobox", font=(FONT, 9)).pack(fill="x", pady=(0, 8))
        self._segmented(card, "Goal", self.f_goal, [("lose", "Lose"), ("maintain", "Maintain"), ("gain", "Gain")])

        self.preview = tk.Label(card, text="", bg=GREEN_SOFT, fg=GREEN_DARK, font=(FONT, 9, "bold"), pady=8)
        self.preview.pack(fill="x", pady=(6, 8))
        self.form_error = tk.Label(card, text="", bg=CARD, fg=RED, font=(FONT, 8), justify="left", wraplength=270)
        self.form_error.pack(anchor="w")
        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", pady=(4, 0))
        self._button(buttons, "Save profile", self._save_form, primary=True).pack(side="left")
        if self.profile is not None:
            self._button(buttons, "Cancel", self._render_side).pack(side="left", padx=8)
        for var in (self.f_age, self.f_height, self.f_weight, self.f_sex, self.f_goal, self.f_activity):
            var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _entry(self, parent, label, var):
        tk.Label(parent, text=label, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 2))
        tk.Entry(parent, textvariable=var, width=1, bg="#f8faf7", fg=TEXT, relief="flat", font=(FONT, 10),
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=GREEN,
                 insertbackground=TEXT).pack(fill="x", ipady=5, pady=(0, 8))

    def _segmented(self, parent, label, var, options):
        tk.Label(parent, text=label, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 2))
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, 8))
        buttons = {}

        def paint(*_):
            for value, btn in buttons.items():
                chosen = var.get() == value
                btn.configure(bg=GREEN if chosen else "#f1f4ef", fg="#ffffff" if chosen else TEXT)

        for value, text in options:
            btn = tk.Label(row, text=text, font=(FONT, 9, "bold"), pady=6, cursor="hand2")
            btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            btn.bind("<Button-1>", lambda _e, v=value: var.set(v))
            buttons[value] = btn
        var.trace_add("write", paint)
        paint()

    def _form_profile(self):
        activity = next(k for k, v in ACTIVITY_LABELS.items() if v == self.f_activity.get())
        return Profile(name=self.f_name.get().strip(), age=int(self.f_age.get()), sex=self.f_sex.get(),
                       height_cm=float(self.f_height.get()), weight_kg=float(self.f_weight.get()),
                       activity=activity, goal=self.f_goal.get())

    def _update_preview(self):
        try:
            profile = self._form_profile()
            problems = profile.validate()
            if problems:
                raise ValueError(problems[0])
            self.preview.configure(text=f"BMI {profile.bmi:.1f} · {profile.bmi_category} · "
                                        f"{profile.calorie_target:,} kcal/day")
        except (ValueError, StopIteration):
            self.preview.configure(text="Enter age, height and weight")

    def _save_form(self):
        try:
            profile = self._form_profile()
        except (ValueError, StopIteration):
            self.form_error.configure(text="Age, height and weight must be numbers.")
            return
        problems = profile.validate()
        if problems:
            self.form_error.configure(text="\n".join(problems))
            return
        self.profile = profile
        save_profile(profile)
        self._render_side()
        self._refresh_suggestions()

    def _profile_summary(self):
        p = self.profile
        card = self._card(self.side)
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=f"Hi{', ' + p.name if p.name else ''}!", bg=CARD, fg=TEXT,
                 font=(FONT, 13, "bold")).pack(side="left")
        edit = tk.Label(head, text="Edit", bg=CARD, fg=GREEN, font=(FONT, 9, "bold"), cursor="hand2")
        edit.pack(side="right")
        edit.bind("<Button-1>", lambda _e: self._edit_profile())
        tk.Label(card, text=f"{p.age} y · {p.height_cm:g} cm · {p.weight_kg:g} kg · goal: {p.goal}",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(2, 12))
        self._bmi_gauge(card, p.bmi, p.bmi_category)

        tiles = tk.Frame(card, bg=CARD)
        tiles.pack(fill="x", pady=(14, 0))
        low, high = p.protein_range_g
        stats = [("Calories", f"{p.calorie_target:,}", "kcal / day", ORANGE),
                 ("Water", f"{p.water_litres}", "litres / day", BLUE),
                 ("Protein", f"{low}-{high}", "grams / day", GREEN),
                 ("Activity", ACTIVITY_LABELS[p.activity].split(" (")[0], "level", "#7b6fd6")]
        for index, (label, value, unit, color) in enumerate(stats):
            tile = tk.Frame(tiles, bg="#f8faf7", padx=12, pady=10)
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 8) if index % 2 == 0 else 0, pady=4)
            tk.Frame(tile, bg=color, width=4, height=34).pack(side="left", padx=(0, 10))
            text = tk.Frame(tile, bg="#f8faf7")
            text.pack(side="left")
            tk.Label(text, text=label, bg="#f8faf7", fg=MUTED, font=(FONT, 8)).pack(anchor="w")
            tk.Label(text, text=value, bg="#f8faf7", fg=TEXT, font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(text, text=unit, bg="#f8faf7", fg=MUTED, font=(FONT, 7)).pack(anchor="w")
        tiles.columnconfigure((0, 1), weight=1, uniform="tile")

        tk.Checkbutton(card, text="Use my profile in answers", variable=self.use_profile, bg=CARD, fg=TEXT,
                       activebackground=CARD, selectcolor=GREEN_SOFT, font=(FONT, 9),
                       cursor="hand2").pack(anchor="w", pady=(12, 0))

        tip = self._card(self.side, "Today's tip")
        tk.Label(tip, text=self._tip(p), bg=CARD, fg=TEXT, font=(FONT, 9), justify="left",
                 wraplength=280).pack(anchor="w")

    def _edit_profile(self):
        for child in self.side.winfo_children():
            child.destroy()
        self._profile_form()

    def _bmi_gauge(self, parent, bmi, category):
        width, top = 290, 26
        canvas = tk.Canvas(parent, width=width, height=74, bg=CARD, highlightthickness=0)
        canvas.pack(anchor="w")
        low, high = 15.0, 40.0
        to_x = lambda value: (min(max(value, low), high) - low) / (high - low) * width
        for start, end, color in ((15, 18.5, BLUE), (18.5, 25, GREEN), (25, 30, ORANGE), (30, 40, RED)):
            canvas.create_rectangle(to_x(start), top, to_x(end), top + 10, fill=color, outline="")
        x = to_x(bmi)
        canvas.create_polygon(x - 6, top - 9, x + 6, top - 9, x, top - 1, fill=TEXT, outline="")
        canvas.create_text(min(max(x, 40), width - 40), 8, text=f"BMI {bmi:.1f}", fill=TEXT, font=(FONT, 9, "bold"))
        for value in (18.5, 25, 30):
            canvas.create_text(to_x(value), top + 22, text=f"{value:g}", fill=MUTED, font=(FONT, 7))
        canvas.create_text(width / 2, top + 34, text=category, fill=MUTED, font=(FONT, 8))

    @staticmethod
    def _tip(p):
        if p.goal == "lose":
            return (f"Aim for about {p.calorie_target:,} kcal a day: fill half your plate with vegetables "
                    "and keep protein in every meal to stay full.")
        if p.goal == "gain":
            return (f"Aim for about {p.calorie_target:,} kcal a day with regular strength training and "
                    f"{p.protein_range_g[1]} g protein to build muscle.")
        return (f"Keep around {p.calorie_target:,} kcal a day, move at least 30 minutes, "
                f"and drink about {p.water_litres} L of water.")

    # ------------------------------------------------------------------ chat
    def _build_chat(self, parent):
        panel = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        panel.pack(side="left", fill="both", expand=True, padx=(16, 0))

        topics = tk.Frame(panel, bg=CARD, padx=20, pady=14)
        topics.pack(fill="x")
        tk.Label(topics, text="Topics", bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left", padx=(0, 10))
        self.chips = {}
        for name, (color, _) in TOPICS.items():
            chip = tk.Label(topics, text=f"●  {name}", font=(FONT, 9, "bold"), padx=12, pady=6, cursor="hand2")
            chip.pack(side="left", padx=3)
            chip.bind("<Button-1>", lambda _e, n=name: self._select_topic(n))
            self.chips[name] = chip
        self.suggest_row = tk.Frame(panel, bg=CARD, padx=20)
        self.suggest_row.pack(fill="x", pady=(0, 10))
        tk.Frame(panel, bg=LINE, height=1).pack(fill="x")

        feed_wrap = tk.Frame(panel, bg=CARD)
        feed_wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(feed_wrap, bg=CARD, highlightthickness=0)
        bar = ttk.Scrollbar(feed_wrap, orient="vertical", command=self.canvas.yview, style="Feed.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.feed = tk.Frame(self.canvas, bg=CARD)
        self.feed_id = self.canvas.create_window((0, 0), window=self.feed, anchor="nw")
        self.feed.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Enter>", lambda _e: self.root.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _e: self.root.unbind_all("<MouseWheel>"))

        composer = tk.Frame(panel, bg=CARD, padx=20, pady=14)
        composer.pack(fill="x")
        box = tk.Frame(composer, bg="#f8faf7", highlightthickness=1, highlightbackground=LINE,
                       highlightcolor=GREEN, padx=12, pady=8)
        box.pack(fill="x")
        self.input = tk.Text(box, height=2, wrap="word", bg="#f8faf7", fg=TEXT, relief="flat", bd=0,
                             font=(FONT, 11), insertbackground=TEXT)
        self.input.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.input.bind("<Return>", self._on_enter)
        self.send_btn = self._button(box, "Send", self._send_or_stop, primary=True)
        self.send_btn.pack(side="right")
        self.send_btn.configure(state="disabled")
        tk.Label(composer, text="General wellness information, not medical advice. "
                                "For health problems, talk to a doctor.",
                 bg=CARD, fg=MUTED, font=(FONT, 8)).pack(anchor="w", pady=(8, 0))

    def _select_topic(self, name):
        self.topic = name
        for topic, chip in self.chips.items():
            color = TOPICS[topic][0]
            chosen = topic == name
            chip.configure(bg=color if chosen else "#f1f4ef", fg="#ffffff" if chosen else color)
        self._refresh_suggestions()

    def _refresh_suggestions(self):
        for child in self.suggest_row.winfo_children():
            child.destroy()
        questions = list(TOPICS[self.topic][1])
        if self.profile is not None and self.topic == "Nutrition":
            questions[0] = f"Make a one-day meal plan for about {self.profile.calorie_target} kcal"
        for question in questions:
            pill = tk.Label(self.suggest_row, text=question, bg=GREEN_SOFT, fg=GREEN_DARK, font=(FONT, 9),
                            padx=10, pady=5, cursor="hand2")
            pill.pack(side="left", padx=(0, 6))
            pill.bind("<Button-1>", lambda _e, q=question: self.send(q))
            pill.bind("<Enter>", lambda _e, w=pill: w.configure(bg="#cdebd9"))
            pill.bind("<Leave>", lambda _e, w=pill: w.configure(bg=GREEN_SOFT))

    def _welcome(self):
        box = tk.Frame(self.feed, bg=CARD)
        box.pack(fill="x", padx=28, pady=(26, 8))
        self._avatar(box).pack(side="left", anchor="n", padx=(0, 12))
        bubble = tk.Label(box, text="Hi! I'm HealthyCoach. Ask me about healthy food, workouts, sleep, stress "
                                    "or drinking enough water. Pick a topic above or type your own question.\n\n"
                                    "Tip: fill in your health profile on the left for personal answers.",
                          bg="#f1f7f3", fg=TEXT, font=(FONT, 10), justify="left", wraplength=self.wrap,
                          padx=16, pady=12)
        bubble.pack(side="left", anchor="w")
        self.bubbles.append(bubble)

    def _avatar(self, parent):
        avatar = tk.Canvas(parent, width=34, height=34, bg=CARD, highlightthickness=0)
        avatar.create_oval(1, 1, 33, 33, fill=GREEN, outline="")
        avatar.create_polygon(17, 8, 26, 17, 17, 27, 8, 17, fill="#ffffff", smooth=True, outline="")
        return avatar

    def _add_message(self, text, from_user):
        row = tk.Frame(self.feed, bg=CARD)
        row.pack(fill="x", padx=28, pady=8)
        meta = None
        if from_user:
            bubble = tk.Label(row, text=text, bg=GREEN, fg="#ffffff", font=(FONT, 10), justify="left",
                              wraplength=self.wrap, padx=16, pady=10)
            bubble.pack(side="right")
        else:
            self._avatar(row).pack(side="left", anchor="n", padx=(0, 12))
            column = tk.Frame(row, bg=CARD)
            column.pack(side="left", fill="x")
            bubble = tk.Label(column, text=text, bg="#f1f7f3", fg=TEXT, font=(FONT, 10), justify="left",
                              wraplength=self.wrap, padx=16, pady=12)
            bubble.pack(anchor="w")
            meta = tk.Label(column, text="", bg=CARD, fg=MUTED, font=(FONT, 8))
            meta.pack(anchor="w", pady=(4, 0))
        bubble.bind("<Button-3>", lambda _e, b=bubble: self._copy(b.cget("text")))
        self.bubbles.append(bubble)
        self._scroll_down()
        return bubble, meta

    def _on_resize(self, event):
        self.canvas.itemconfigure(self.feed_id, width=event.width)
        self.wrap = max(300, min(680, int(event.width * 0.68)))
        for bubble in self.bubbles:
            bubble.configure(wraplength=self.wrap)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _scroll_down(self):
        self.root.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _button(self, parent, text, command, primary=False):
        bg, hover, fg = (GREEN, GREEN_DARK, "#ffffff") if primary else ("#f1f4ef", LINE, TEXT)
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                        activeforeground=fg, relief="flat", bd=0, padx=18, pady=8, cursor="hand2",
                        font=(FONT, 10, "bold"), disabledforeground="#b8c4bd")
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover) if btn["state"] != "disabled" else None)
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("Copied", "ok")
        self.root.after(1200, lambda: self._set_status("Thinking…" if self.busy else "Ready", "wait" if self.busy else "ok"))

    # ------------------------------------------------------------ model work
    def _start_loading(self):
        def work():
            started = time.perf_counter()
            try:
                coach = Coach.load()
                self.events.put(("loaded", coach, time.perf_counter() - started))
            except Exception as exc:
                traceback.print_exc()
                self.events.put(("load_failed", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _drain_events(self):
        try:
            while True:
                kind, *data = self.events.get_nowait()
                getattr(self, "_on_" + kind)(*data)
        except queue.Empty:
            pass
        self.root.after(50, self._drain_events)

    def _on_loaded(self, coach, seconds):
        self.coach = coach
        self.device.configure(text=f"{coach.device_name}  ·  loaded in {seconds:.1f} s")
        self._set_status("Ready", "ok")
        self.send_btn.configure(state="normal")
        self.input.focus_set()

    def _on_load_failed(self, error):
        self._set_status("Model not loaded", "bad")
        messagebox.showerror("HealthyCoach", f"{error}\n\nDetails: {LOG_FILE}")

    def _on_partial(self, text):
        if self.answer_label is not None:
            self.answer_label.configure(text=text.strip() or "…")
            self._scroll_down()

    def _on_finished(self, text, stopped):
        seconds = time.perf_counter() - self.started_at
        self.answer_label.configure(text=text.strip() or "Sorry, I couldn't answer that. Please try again.")
        self.answer_meta.configure(text=f"{seconds:.1f} s" + ("  ·  stopped" if stopped else "")
                                   + ("  ·  personalised" if self._personal() else ""))
        self._done()

    def _on_failed(self, error):
        self.answer_label.configure(text=f"Error: {error[:600]}", fg=RED)
        self._done()

    def _done(self):
        self.busy = False
        self.answer_label = self.answer_meta = None
        self.send_btn.configure(text="Send", state="normal")
        self._set_status("Ready", "ok")
        self.input.focus_set()

    def _personal(self):
        return self.profile is not None and self.use_profile.get()

    # --------------------------------------------------------------- actions
    def _on_enter(self, event):
        if event.state & 0x0001:  # Shift+Enter: new line
            return None
        if not self.busy:
            self.send()
        return "break"

    def _send_or_stop(self):
        if self.busy:
            self.stop_event.set()
            self.send_btn.configure(text="Stopping…", state="disabled")
        else:
            self.send()

    def send(self, question=None):
        if self.busy or self.coach is None:
            return
        if question is None:
            question = self.input.get("1.0", "end-1c").strip()
            if not question:
                return
            self.input.delete("1.0", "end")
        self._add_message(question, from_user=True)
        self.answer_label, self.answer_meta = self._add_message("…", from_user=False)
        self.busy = True
        self.stop_event.clear()
        self.started_at = time.perf_counter()
        self.send_btn.configure(text="Stop")
        self._set_status("Thinking…", "wait")
        profile = self.profile if self._personal() else None

        def work():
            text = ""
            try:
                for text in self.coach.stream(question, profile, stop_event=self.stop_event):
                    self.events.put(("partial", text))
                self.events.put(("finished", text, self.stop_event.is_set()))
            except Exception as exc:
                traceback.print_exc()
                self.events.put(("failed", str(exc)))
        threading.Thread(target=work, daemon=True).start()


def main():
    root = tk.Tk()
    HealthyCoachApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
