import configparser
import os
import re  # <--- Dodane do naturalnego sortowania liczb w nazwach plików
import shutil
import struct
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

# Główne ścieżki docelowe wewnątrz gogli Quest
REMOTE_INI = "/sdcard/vlmn/TWD/Saved/Config/Android/GameUserSettings.ini"
REMOTE_SAVES_BASE = "/sdcard/vlmn/TWD/Saved/SaveGames"

# Pliki lokalne zapisywane są w podfolderach obok skryptu
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SETTINGS_DIR = os.path.join(_BASE_DIR, "Settings")
_TEMP_SAVES_DIR = os.path.join(_SETTINGS_DIR, "TempSaves")
_BACKUP_SAVES_DIR = os.path.join(_BASE_DIR, "SavesBackup")

os.makedirs(_SETTINGS_DIR, exist_ok=True)
os.makedirs(_TEMP_SAVES_DIR, exist_ok=True)
os.makedirs(_BACKUP_SAVES_DIR, exist_ok=True)

LOCAL_INI = os.path.join(_SETTINGS_DIR, "temp_GameUserSettings.ini")

# Paleta kolorów - Material You (Dark Theme / Pastel Blue Accent)
SURFACE = "#1E1F22"  # Tło okna głównego
SURFACE_CONTAINER = "#2B2D30"  # Tło kart i paneli bocznych
SURFACE_CONTAINER_HIGH = (
    "#393B40"  # Tło pól tekstowych i aktywnych przycisków nawigacji
)
ACCENT_PRIMARY = "#A8C7FA"  # Główny pastelowy błękit Material You
ACCENT_ON_PRIMARY = "#062E6F"  # Ciemny, kontrastowy tekst na przyciskach akcji
TEXT_MAIN = "#E3E3E3"  # Podstawowy jasny tekst
TEXT_MUTED = "#8E9094"  # Tekst pomocniczy i opisy


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


class MaterialSwitch(tk.Canvas):
    """Płynny, animowany przełącznik w stylu Material You."""

    WIDTH = 56
    HEIGHT = 30
    PAD = 3
    SUPERSAMPLE = 4

    def __init__(
        self, parent, command=None, initial=False, bg_parent=SURFACE_CONTAINER
    ):
        super().__init__(
            parent,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=bg_parent,
            highlightthickness=0,
            cursor="hand2",
        )
        self.command = command
        self.state = initial
        self._locked = False
        self.bg_parent_rgb = _hex_to_rgb(bg_parent)

        self.knob_d = self.HEIGHT - 2 * self.PAD
        self.min_x = self.PAD
        self.max_x = self.WIDTH - self.knob_d - self.PAD

        self.cur_x = self.max_x if initial else self.min_x

        self._photo = None
        self._image_id = self.create_image(0, 0, anchor="nw")

        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _on_click(self, _event=None):
        if self._locked:
            return
        self._locked = True

        self.state = not self.state
        target_x = self.max_x if self.state else self.min_x

        self._animate(target_x)

        if self.command:
            self.after(150, self._execute_command)
        else:
            self._locked = False

    def _execute_command(self):
        self.command()
        self._locked = False

    def set_state(self, value: bool, animate=False):
        new_state = bool(value)
        if self.state != new_state:
            self.state = new_state
            target_x = self.max_x if self.state else self.min_x
            if animate:
                self._animate(target_x)
            else:
                self.cur_x = target_x
                self._draw()
        else:
            target_x = self.max_x if self.state else self.min_x
            if abs(self.cur_x - target_x) > 0.5:
                self.cur_x = target_x
                self._draw()

    def _animate(self, target_x):
        diff = target_x - self.cur_x
        if abs(diff) < 0.5:
            self.cur_x = target_x
            self._draw()
            return

        self.cur_x += diff * 0.35
        self._draw()
        self.after(16, lambda: self._animate(target_x))

    def _draw(self):
        track_color = (
            ACCENT_PRIMARY if self.state else SURFACE_CONTAINER_HIGH
        )
        knob_color = ACCENT_ON_PRIMARY if self.state else TEXT_MUTED

        s = self.SUPERSAMPLE
        w, h = self.WIDTH * s, self.HEIGHT * s

        img = Image.new("RGBA", (w, h), self.bg_parent_rgb + (255,))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [0, 0, w - 1, h - 1],
            radius=h / 2,
            fill=_hex_to_rgb(track_color),
        )

        kx = self.cur_x * s
        kpad = self.PAD * s
        kd = self.knob_d * s
        draw.ellipse(
            [kx, kpad, kx + kd, kpad + kd], fill=_hex_to_rgb(knob_color)
        )

        img = img.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.itemconfig(self._image_id, image=self._photo)


class TWDMaterialModder(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("VLMN TWD Saints & Sinners Modder")
        self.geometry("820x640")
        self.configure(bg=SURFACE)

        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        self.settings_entries = {}

        self.adb_path = self.find_adb()

        self.create_layout()
        self.switch_tab("actions")

    def find_adb(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pt_adb = os.path.join(
            base_dir, "platform-tools", "adb.exe" if os.name == "nt" else "adb"
        )
        if os.path.exists(pt_adb):
            return pt_adb

        local_adb = os.path.join(
            base_dir, "adb.exe" if os.name == "nt" else "adb"
        )
        if os.path.exists(local_adb):
            return local_adb

        return "adb"

    def adb_command(self, args):
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            res = subprocess.run(
                [self.adb_path] + args,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
            )
            ok = res.returncode == 0
            if ok:
                return ok, (res.stdout.strip() or res.stderr.strip() or "OK")
            return ok, (
                res.stderr.strip() or res.stdout.strip() or "Błąd polecenia ADB"
            )
        except Exception as e:
            return False, str(e)

    def pull_file(self):
        success, out = self.adb_command(["pull", REMOTE_INI, LOCAL_INI])
        if success and not os.path.exists(LOCAL_INI):
            return False, f"Błąd odczytu pliku z Questa.\nSzczegóły: {out}"
        return success and os.path.exists(LOCAL_INI), out

    def push_file(self):
        return self.adb_command(["push", LOCAL_INI, REMOTE_INI])

    # --- BEZPIECZNE FUNKCJE PARSOWANIA BINARNEGO GVAS (Z POPRAWKĄ +9 BAJTÓW) ---

    def read_gvas_float(self, data: bytes, prop_name: bytes):
        pos = data.find(prop_name + b"\x00")
        if pos == -1:
            pos = data.find(prop_name)
        if pos != -1:
            type_pos = data.find(b"FloatProperty\x00", pos)
            if type_pos != -1:
                val_offset = type_pos + len(b"FloatProperty\x00") + 9
                if val_offset + 4 <= len(data):
                    val = struct.unpack(
                        "<f", data[val_offset : val_offset + 4]
                    )[0]
                    return val, val_offset
        return None, -1

    def read_gvas_int(self, data: bytes, prop_name: bytes):
        pos = data.find(prop_name + b"\x00")
        if pos == -1:
            pos = data.find(prop_name)
        if pos != -1:
            type_pos = data.find(b"IntProperty\x00", pos)
            if type_pos != -1:
                val_offset = type_pos + len(b"IntProperty\x00") + 9
                if val_offset + 4 <= len(data):
                    val = struct.unpack(
                        "<i", data[val_offset : val_offset + 4]
                    )[0]
                    return val, val_offset
        return None, -1

    def read_gvas_string(self, data: bytes, prop_name: bytes):
        pos = data.find(prop_name + b"\x00")
        if pos == -1:
            pos = data.find(prop_name)
        if pos != -1:
            type_pos = data.find(b"StrProperty\x00", pos)
            if type_pos != -1:
                val_offset = type_pos + len(b"StrProperty\x00") + 9
                if val_offset + 4 <= len(data):
                    length = struct.unpack(
                        "<i", data[val_offset : val_offset + 4]
                    )[0]
                    if 0 < length < 500 and val_offset + 4 + length <= len(
                        data
                    ):
                        raw_bytes = data[
                            val_offset + 4 : val_offset + 4 + length - 1
                        ]
                        return (
                            raw_bytes.decode("utf-8", errors="replace"),
                            val_offset,
                        )
        return "Brak danych", -1

    def create_layout(self):
        # --- PANEL BOCZNY (Poszerzony do 220px, aby pełny tytuł się nie zawijał) ---
        self.nav_frame = tk.Frame(self, bg=SURFACE_CONTAINER, width=220)
        self.nav_frame.pack(side="left", fill="y")
        self.nav_frame.pack_propagate(False)

        lbl_app_title = tk.Label(
            self.nav_frame,
            text="VLMN TWD Modder",
            font=("Segoe UI", 14, "bold"),
            bg=SURFACE_CONTAINER,
            fg=ACCENT_PRIMARY,
        )
        # Symetryczny margines pionowy (28px w górę i w dół) po usunięciu tekstu ADB
        lbl_app_title.pack(pady=(28, 28), padx=14, anchor="w")

        self.btn_tab_actions = tk.Button(
            self.nav_frame,
            text="Szybkie akcje",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            anchor="w",
            padx=16,
            pady=12,
            command=lambda: self.switch_tab("actions"),
        )
        self.btn_tab_actions.pack(fill="x", padx=10, pady=4)

        self.btn_tab_settings = tk.Button(
            self.nav_frame,
            text="Pełny plik .ini",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            anchor="w",
            padx=16,
            pady=12,
            command=lambda: self.switch_tab("settings"),
        )
        self.btn_tab_settings.pack(fill="x", padx=10, pady=4)

        self.btn_tab_saves = tk.Button(
            self.nav_frame,
            text="Zarządzanie zapisami",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            anchor="w",
            padx=16,
            pady=12,
            command=lambda: self.switch_tab("saves"),
        )
        self.btn_tab_saves.pack(fill="x", padx=10, pady=4)

        lbl_ai_footer = tk.Label(
            self.nav_frame,
            text="Stworzone z pomocą AI",
            font=("Segoe UI", 8),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
        )
        lbl_ai_footer.pack(side="bottom", pady=(0, 14), padx=16, anchor="w")

        # --- OBSZAR GŁÓWNY ---
        self.content_frame = tk.Frame(self, bg=SURFACE)
        self.content_frame.pack(side="right", fill="both", expand=True)

        self.view_actions = tk.Frame(self.content_frame, bg=SURFACE)
        self.create_actions_view()

        self.view_settings = tk.Frame(self.content_frame, bg=SURFACE)
        self.create_settings_view()

        self.view_saves = tk.Frame(self.content_frame, bg=SURFACE)
        self.create_saves_view()

    def switch_tab(self, tab):
        self.view_actions.pack_forget()
        self.view_settings.pack_forget()
        self.view_saves.pack_forget()

        self.btn_tab_actions.config(bg=SURFACE_CONTAINER, fg=TEXT_MUTED)
        self.btn_tab_settings.config(bg=SURFACE_CONTAINER, fg=TEXT_MUTED)
        self.btn_tab_saves.config(bg=SURFACE_CONTAINER, fg=TEXT_MUTED)

        if tab == "actions":
            self.view_actions.pack(fill="both", expand=True, padx=28, pady=28)
            self.btn_tab_actions.config(
                bg=SURFACE_CONTAINER_HIGH, fg=ACCENT_PRIMARY
            )
            self.update_sinner_status_label()
        elif tab == "settings":
            self.view_settings.pack(fill="both", expand=True, padx=28, pady=28)
            self.btn_tab_settings.config(
                bg=SURFACE_CONTAINER_HIGH, fg=ACCENT_PRIMARY
            )
            if not self.settings_entries:
                self.load_settings_into_gui()
        elif tab == "saves":
            self.view_saves.pack(fill="both", expand=True, padx=28, pady=28)
            self.btn_tab_saves.config(
                bg=SURFACE_CONTAINER_HIGH, fg=ACCENT_PRIMARY
            )
            self.detect_profiles_and_saves()

    def create_actions_view(self):
        lbl_header = tk.Label(
            self.view_actions,
            text="Panel zarządzania",
            font=("Segoe UI", 20, "bold"),
            bg=SURFACE,
            fg=TEXT_MAIN,
        )
        lbl_header.pack(anchor="w", pady=(0, 24))

        card_perm = tk.Frame(
            self.view_actions, bg=SURFACE_CONTAINER, padx=24, pady=20
        )
        card_perm.pack(fill="x", pady=(0, 20))

        lbl_p_title = tk.Label(
            card_perm,
            text="Uprawnienie do zarządzania pamięcią",
            font=("Segoe UI", 12, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_p_title.pack(anchor="w")

        lbl_p_desc = tk.Label(
            card_perm,
            text="Wymusza przez polecenie AppOps pełny dostęp do pamięci masowej Questa. Niezbędne, aby silnik gry mógł swobodnie zapisywać i odczytywać pliki z katalogu vlmn.",
            font=("Segoe UI", 10),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
            wraplength=480,
            justify="left",
        )
        lbl_p_desc.pack(anchor="w", pady=(4, 16))

        btn_p_run = tk.Button(
            card_perm,
            text="[ Grant Storage Permission ]",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT_PRIMARY,
            fg=ACCENT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=20,
            pady=8,
            command=self.action_grant_permission,
        )
        btn_p_run.pack(anchor="w")

        card_sinner = tk.Frame(
            self.view_actions, bg=SURFACE_CONTAINER, padx=24, pady=20
        )
        card_sinner.pack(fill="x")

        lbl_s_title = tk.Label(
            card_sinner,
            text="Sinners Mode",
            font=("Segoe UI", 12, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_s_title.pack(anchor="w")

        lbl_s_desc = tk.Label(
            card_sinner,
            text="Aktywuje ukryty tryb ułatwień i opcji deweloperskich wewnątrz gry (parametr bSinner).",
            font=("Segoe UI", 10),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
            wraplength=480,
            justify="left",
        )
        lbl_s_desc.pack(anchor="w", pady=(4, 12))

        self.lbl_sinner_status = tk.Label(
            card_sinner,
            text="Status: Sprawdzanie stanu na goglach...",
            font=("Segoe UI", 10, "italic"),
            bg=SURFACE_CONTAINER,
            fg=ACCENT_PRIMARY,
        )
        self.lbl_sinner_status.pack(anchor="w", pady=(0, 16))

        row_sinner_switch = tk.Frame(card_sinner, bg=SURFACE_CONTAINER)
        row_sinner_switch.pack(anchor="w")

        self.sinner_switch = MaterialSwitch(
            row_sinner_switch,
            command=self.action_toggle_sinner,
            initial=False,
            bg_parent=SURFACE_CONTAINER,
        )
        self.sinner_switch.pack(side="left")

        lbl_switch_caption = tk.Label(
            row_sinner_switch,
            text="Przełącznik Sinners Mode",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_switch_caption.pack(side="left", padx=(10, 0))

    def create_settings_view(self):
        top_bar = tk.Frame(self.view_settings, bg=SURFACE)
        top_bar.pack(fill="x", pady=(0, 16))

        lbl_s_header = tk.Label(
            top_bar,
            text="Edytor ustawień",
            font=("Segoe UI", 20, "bold"),
            bg=SURFACE,
            fg=TEXT_MAIN,
        )
        lbl_s_header.pack(side="left")

        btn_save = tk.Button(
            top_bar,
            text="[ Zapisz na Questa ]",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT_PRIMARY,
            fg=ACCENT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self.save_settings_from_gui,
        )
        btn_save.pack(side="right")

        btn_load = tk.Button(
            top_bar,
            text="[ Pobierz z gogli ]",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self.load_settings_into_gui,
        )
        btn_load.pack(side="right", padx=(0, 12))

        self.canvas = tk.Canvas(
            self.view_settings,
            bg=SURFACE,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(
            self.view_settings,
            orient="vertical",
            command=self.canvas.yview,
            bg=SURFACE_CONTAINER,
            borderwidth=0,
        )
        self.scroll_frame = tk.Frame(self.canvas, bg=SURFACE)

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(
                self.canvas_window, width=e.width
            ),
        )
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )

        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

    # --- ZAKŁADKA 3: ZARZĄDZANIE ZAPISAMI (SAVY) ---

    def create_saves_view(self):
        top_bar = tk.Frame(self.view_saves, bg=SURFACE)
        top_bar.pack(fill="x", pady=(0, 16))

        lbl_header = tk.Label(
            top_bar,
            text="Zapisy gry (Savy)",
            font=("Segoe UI", 20, "bold"),
            bg=SURFACE,
            fg=TEXT_MAIN,
        )
        lbl_header.pack(side="left")

        btn_refresh = tk.Button(
            top_bar,
            text="[ Odśwież listę ]",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT_PRIMARY,
            fg=ACCENT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=14,
            pady=6,
            command=self.detect_profiles_and_saves,
        )
        btn_refresh.pack(side="right")

        profile_box = tk.Frame(
            self.view_saves, bg=SURFACE_CONTAINER, padx=16, pady=12
        )
        profile_box.pack(fill="x", pady=(0, 16))

        lbl_p = tk.Label(
            profile_box,
            text="Aktywny profil gracza:",
            font=("Segoe UI", 11, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_p.pack(side="left", padx=(0, 12))

        self.combo_profiles = ttk.Combobox(
            profile_box, state="readonly", font=("Segoe UI", 10), width=25
        )
        self.combo_profiles.pack(side="left")
        self.combo_profiles.bind(
            "<<ComboboxSelected>>",
            lambda e: self.load_saves_for_selected_profile(),
        )

        self.saves_canvas = tk.Canvas(
            self.view_saves, bg=SURFACE, borderwidth=0, highlightthickness=0
        )
        s_scrollbar = tk.Scrollbar(
            self.view_saves,
            orient="vertical",
            command=self.saves_canvas.yview,
            bg=SURFACE_CONTAINER,
            borderwidth=0,
        )
        self.saves_scroll_frame = tk.Frame(self.saves_canvas, bg=SURFACE)

        self.saves_canvas_window = self.saves_canvas.create_window(
            (0, 0), window=self.saves_scroll_frame, anchor="nw"
        )

        self.saves_canvas.pack(side="left", fill="both", expand=True)
        s_scrollbar.pack(side="right", fill="y")
        self.saves_canvas.configure(yscrollcommand=s_scrollbar.set)

        self.saves_canvas.bind(
            "<Configure>",
            lambda e: self.saves_canvas.itemconfig(
                self.saves_canvas_window, width=e.width
            ),
        )
        self.saves_scroll_frame.bind(
            "<Configure>",
            lambda e: self.saves_canvas.configure(
                scrollregion=self.saves_canvas.bbox("all")
            ),
        )

        self.saves_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.saves_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

    def detect_profiles_and_saves(self):
        success, out = self.adb_command(["shell", "ls", REMOTE_SAVES_BASE])
        if not success:
            for w in self.saves_scroll_frame.winfo_children():
                w.destroy()
            lbl_err = tk.Label(
                self.saves_scroll_frame,
                text="Nie znaleziono katalogu z profilami na goglach.\nUpewnij się, że gra utworzyła zapisy.",
                font=("Segoe UI", 10),
                bg=SURFACE,
                fg=TEXT_MUTED,
            )
            lbl_err.pack(pady=20)
            return

        raw_items = [line.strip() for line in out.split() if line.strip()]
        profiles = [
            item
            for item in raw_items
            if "Profile" in item or item.startswith("Profile")
        ]

        if not profiles:
            profiles = ["Profile0"]

        self.combo_profiles["values"] = profiles
        if "Profile0" in profiles:
            self.combo_profiles.set("Profile0")
        elif profiles:
            self.combo_profiles.set(profiles[0])

        self.load_saves_for_selected_profile()

    def load_saves_for_selected_profile(self):
        profile = self.combo_profiles.get()
        if not profile:
            return

        for w in self.saves_scroll_frame.winfo_children():
            w.destroy()

        remote_profile_path = f"{REMOTE_SAVES_BASE}/{profile}"
        success, out = self.adb_command(["shell", "ls", remote_profile_path])
        if not success:
            lbl_empty = tk.Label(
                self.saves_scroll_frame,
                text=f"Brak plików w profilu {profile}.",
                font=("Segoe UI", 10),
                bg=SURFACE,
                fg=TEXT_MUTED,
            )
            lbl_empty.pack(pady=20)
            return

        save_files = [
            line.strip()
            for line in out.split()
            if line.strip().endswith(".sav")
        ]
        if not save_files:
            lbl_empty = tk.Label(
                self.saves_scroll_frame,
                text=f"Katalog {profile} jest pusty.",
                font=("Segoe UI", 10),
                bg=SURFACE,
                fg=TEXT_MUTED,
            )
            lbl_empty.pack(pady=20)
            return

        if os.path.exists(_TEMP_SAVES_DIR):
            shutil.rmtree(_TEMP_SAVES_DIR)
        os.makedirs(_TEMP_SAVES_DIR, exist_ok=True)

        # Naturalne sortowanie malejąco (wyciąga cyfrę i układa np. Save12 -> Save11 -> Save1)
        def get_save_number(filename):
            match = re.search(r"\d+", filename)
            return int(match.group()) if match else -1

        sorted_saves = sorted(save_files, key=get_save_number, reverse=True)

        for s_file in sorted_saves:
            remote_file = f"{remote_profile_path}/{s_file}"
            local_file = os.path.join(_TEMP_SAVES_DIR, s_file)

            p_ok, _ = self.adb_command(["pull", remote_file, local_file])
            if p_ok and os.path.exists(local_file):
                self.create_save_card(profile, s_file, local_file)
                # Ta instrukcja sprawia, że karty wczytują się płynnie jedna po drugiej w locie:
                self.saves_scroll_frame.update_idletasks()

    def create_save_card(self, profile, filename, local_filepath):
        card = tk.Frame(
            self.saves_scroll_frame, bg=SURFACE_CONTAINER, padx=20, pady=16
        )
        card.pack(fill="x", pady=(0, 16), padx=(0, 8))

        with open(local_filepath, "rb") as f:
            data = f.read()

        slot_name, _ = self.read_gvas_string(data, b"SaveSlotName")
        seconds, _ = self.read_gvas_float(data, b"TimeInSecondsPlayed")
        day, day_offset = self.read_gvas_int(data, b"CurrentDay")
        health, health_offset = self.read_gvas_float(data, b"CurrentHealth")
        stamina, stamina_offset = self.read_gvas_float(data, b"CurrentStamina")

        if seconds is not None:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            time_str = f"{hours} godz. {minutes} min."
        else:
            time_str = "Brak danych"

        day_str = str(day) if day is not None else "?"
        health_str = f"{health:.1f}" if health is not None else "---"
        stamina_str = f"{stamina:.1f}" if stamina is not None else "---"

        header_frame = tk.Frame(card, bg=SURFACE_CONTAINER)
        header_frame.pack(fill="x")

        lbl_title = tk.Label(
            header_frame,
            text=filename,
            font=("Segoe UI", 14, "bold"),
            bg=SURFACE_CONTAINER,
            fg=ACCENT_PRIMARY,
        )
        lbl_title.pack(side="left")

        lbl_sub = tk.Label(
            header_frame,
            text=f"Wewnętrznie: {slot_name}",
            font=("Segoe UI", 10),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
        )
        lbl_sub.pack(side="left", padx=(12, 0))

        info_frame = tk.Frame(card, bg=SURFACE_CONTAINER)
        info_frame.pack(fill="x", pady=(10, 6))

        lbl_time = tk.Label(
            info_frame,
            text=f"Spędzony czas: {time_str}  |  Dzień w grze: {day_str}",
            font=("Segoe UI", 11),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_time.pack(side="left")

        stats_frame = tk.Frame(card, bg=SURFACE_CONTAINER)
        stats_frame.pack(fill="x", pady=(0, 10))

        lbl_stats = tk.Label(
            stats_frame,
            text=f"Punkty życia: {health_str}  |  Kondycja: {stamina_str}",
            font=("Segoe UI", 10, "italic"),
            bg=SURFACE_CONTAINER,
            fg=ACCENT_PRIMARY,
        )
        lbl_stats.pack(side="left")

        # Rząd 1: Główne operacje na pliku
        actions_frame = tk.Frame(card, bg=SURFACE_CONTAINER)
        actions_frame.pack(fill="x")

        btn_edit = tk.Button(
            actions_frame,
            text="[ Edytuj statystyki ]",
            font=("Segoe UI", 9, "bold"),
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=lambda: self.open_stats_dialog(
                profile,
                filename,
                local_filepath,
                health,
                stamina,
                day,
                health_offset,
                stamina_offset,
                day_offset,
            ),
        )
        btn_edit.pack(side="left", padx=(0, 10))

        btn_rename = tk.Button(
            actions_frame,
            text="[ Zmień nazwę pliku ]",
            font=("Segoe UI", 9, "bold"),
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=lambda: self.rename_save_file(profile, filename),
        )
        btn_rename.pack(side="left", padx=(0, 10))

        btn_backup = tk.Button(
            actions_frame,
            text="[ Kopia zapasowa ]",
            font=("Segoe UI", 9, "bold"),
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=lambda: self.backup_save_file(
                profile, filename, local_filepath
            ),
        )
        btn_backup.pack(side="left")

        # Rząd 2: Niestandardowa amunicja i surowce
        actions_frame_items = tk.Frame(card, bg=SURFACE_CONTAINER)
        actions_frame_items.pack(fill="x", pady=(10, 0))

        btn_items = tk.Button(
            actions_frame_items,
            text="[ Ustaw własną ilość Amunicji i Surowców ]",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT_PRIMARY,
            fg=ACCENT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=lambda: self.inject_custom_ammo_and_quantity(
                profile, filename, local_filepath
            ),
        )
        btn_items.pack(side="left")

    def inject_custom_ammo_and_quantity(
        self, profile, filename, local_filepath
    ):
        val_str = simpledialog.askstring(
            "Modyfikacja zapisu",
            f"Wprowadź pożądaną ilość dla amunicji w magazynkach oraz stosów surowców\nw pliku {filename} (np. 100, 250 lub 500):",
            parent=self,
        )
        if not val_str:
            return

        try:
            new_val = int(val_str)
            if new_val < 0 or new_val > 9999:
                messagebox.showwarning(
                    "Błąd", "Wprowadź liczbę z przedziału od 0 do 9999."
                )
                return
        except ValueError:
            messagebox.showwarning(
                "Błąd", "Wprowadzona wartość musi być liczbą całkowitą."
            )
            return

        with open(local_filepath, "rb") as f:
            data = bytearray(f.read())

        count_replaced = 0
        new_bytes = struct.pack("<i", new_val)

        target_q = b"quantity\x00IntProperty\x00"
        pos = 0
        while True:
            pos = data.find(target_q, pos)
            if pos == -1:
                break
            val_idx = pos + len(target_q) + 9
            if val_idx + 4 <= len(data):
                data[val_idx : val_idx + 4] = new_bytes
                count_replaced += 1
            pos += len(target_q)

        target_a = b"\x05\x00\x00\x00Ammo\x00"
        pos = 0
        while True:
            pos = data.find(target_a, pos)
            if pos == -1:
                break
            val_idx = pos + len(target_a)
            if val_idx + 4 <= len(data):
                data[val_idx : val_idx + 4] = new_bytes
                count_replaced += 1
            pos += len(target_a)

        if count_replaced == 0:
            messagebox.showinfo(
                "Informacja",
                "W tym zapisie nie znaleziono żadnej broni z amunicją ani zebranych przedmiotów.",
            )
            return

        with open(local_filepath, "wb") as f:
            f.write(data)

        remote_file = f"{REMOTE_SAVES_BASE}/{profile}/{filename}"
        success, err = self.adb_command(["push", local_filepath, remote_file])
        if success:
            messagebox.showinfo(
                "Sukces",
                f"Zaktualizowano {count_replaced} pozycji w ekwipunku na wartość: {new_val}!",
            )
            self.load_saves_for_selected_profile()
        else:
            messagebox.showerror(
                "Błąd ADB", f"Odmowa zapisu na goglach:\n{err}"
            )

    def open_stats_dialog(
        self,
        profile,
        filename,
        local_filepath,
        cur_health,
        cur_stamina,
        cur_day,
        h_off,
        s_off,
        d_off,
    ):
        dialog = tk.Toplevel(self)
        dialog.title(f"Edycja zapisu: {filename}")
        dialog.geometry("380x320")
        dialog.configure(bg=SURFACE_CONTAINER)
        dialog.transient(self)
        dialog.grab_set()

        lbl_top = tk.Label(
            dialog,
            text="Wprowadź nowe wartości",
            font=("Segoe UI", 14, "bold"),
            bg=SURFACE_CONTAINER,
            fg=TEXT_MAIN,
        )
        lbl_top.pack(pady=(16, 12))

        box = tk.Frame(dialog, bg=SURFACE_CONTAINER)
        box.pack(fill="both", expand=True, padx=20)

        tk.Label(
            box,
            text="Punkty życia (np. 100.0):",
            bg=SURFACE_CONTAINER,
            fg=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", pady=6)
        ent_h = tk.Entry(
            box,
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=4,
            width=15,
        )
        if cur_health is not None:
            ent_h.insert(0, str(cur_health))
        ent_h.grid(row=0, column=1, padx=10, pady=6)

        tk.Label(
            box, text="Kondycja (np. 100.0):", bg=SURFACE_CONTAINER, fg=TEXT_MUTED
        ).grid(row=1, column=0, sticky="w", pady=6)
        ent_s = tk.Entry(
            box,
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=4,
            width=15,
        )
        if cur_stamina is not None:
            ent_s.insert(0, str(cur_stamina))
        ent_s.grid(row=1, column=1, padx=10, pady=6)

        tk.Label(
            box, text="Dzień w grze:", bg=SURFACE_CONTAINER, fg=TEXT_MUTED
        ).grid(row=2, column=0, sticky="w", pady=6)
        ent_d = tk.Entry(
            box,
            bg=SURFACE_CONTAINER_HIGH,
            fg=TEXT_MAIN,
            relief="flat",
            borderwidth=4,
            width=15,
        )
        if cur_day is not None:
            ent_d.insert(0, str(cur_day))
        ent_d.grid(row=2, column=1, padx=10, pady=6)

        def save_changes():
            try:
                new_h = float(ent_h.get())
                new_s = float(ent_s.get())
                new_d = int(ent_d.get())

                with open(local_filepath, "rb") as f:
                    data = bytearray(f.read())

                if h_off != -1:
                    data[h_off : h_off + 4] = struct.pack("<f", new_h)
                if s_off != -1:
                    data[s_off : s_off + 4] = struct.pack("<f", new_s)
                if d_off != -1:
                    data[d_off : d_off + 4] = struct.pack("<i", new_d)

                with open(local_filepath, "wb") as f:
                    f.write(data)

                remote_file = f"{REMOTE_SAVES_BASE}/{profile}/{filename}"
                success, err = self.adb_command(
                    ["push", local_filepath, remote_file]
                )
                if success:
                    dialog.destroy()
                    messagebox.showinfo(
                        "Sukces", "Statystyki zaktualizowane na goglach!"
                    )
                    self.load_saves_for_selected_profile()
                else:
                    messagebox.showerror(
                        "Błąd ADB", f"Odmowa wysłania pliku:\n{err}"
                    )

            except ValueError:
                messagebox.showerror(
                    "Błąd formatu", "Wprowadzono niepoprawne liczby."
                )
            except Exception as e:
                messagebox.showerror("Błąd", f"Wystąpił problem:\n{str(e)}")

        btn_commit = tk.Button(
            dialog,
            text="[ Zapisz i wyślij ]",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT_PRIMARY,
            fg=ACCENT_ON_PRIMARY,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            pady=8,
            command=save_changes,
        )
        btn_commit.pack(fill="x", padx=20, pady=(10, 20))

    def rename_save_file(self, profile, old_filename):
        new_name = simpledialog.askstring(
            "Zmiana nazwy",
            f"Wprowadź nową nazwę dla pliku {old_filename}\n(pamiętaj o rozszerzeniu .sav):",
            initialvalue=old_filename,
            parent=self,
        )
        if not new_name or new_name == old_filename:
            return

        if not new_name.lower().endswith(".sav"):
            new_name += ".sav"

        remote_old = f"{REMOTE_SAVES_BASE}/{profile}/{old_filename}"
        remote_new = f"{REMOTE_SAVES_BASE}/{profile}/{new_name}"

        success, err = self.adb_command(
            ["shell", "mv", f'"{remote_old}"', f'"{remote_new}"']
        )
        if success:
            messagebox.showinfo(
                "Zmiana nazwy", f"Plik przemianowany na {new_name}."
            )
            self.load_saves_for_selected_profile()
        else:
            messagebox.showerror("Błąd ADB", f"Odmowa zmiany nazwy:\n{err}")

    def backup_save_file(self, profile, filename, local_filepath):
        target_dir = os.path.join(_BACKUP_SAVES_DIR, profile)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, filename)

        try:
            shutil.copyfile(local_filepath, target_path)
            messagebox.showinfo(
                "Kopia zapasowa", f"Zapisano kopię w folderze:\n{target_path}"
            )
        except Exception as e:
            messagebox.showerror(
                "Błąd", f"Nie udało się skopiować pliku:\n{str(e)}"
            )

    # --- POZOSTAŁE METODY PANELU AKCJI I INI ---

    def action_grant_permission(self):
        cmd = [
            "shell",
            "appops",
            "set",
            "com.SDI.TWD",
            "MANAGE_EXTERNAL_STORAGE",
            "allow",
        ]
        success, out = self.adb_command(cmd)
        if success:
            messagebox.showinfo(
                "Sukces", "Uprawnienie zapisu zostało pomyślnie wymuszone!"
            )
        else:
            messagebox.showerror(
                "Błąd operacji ADB", f"System odrzucił żądanie:\n{out}"
            )

    def action_toggle_sinner(self):
        success, err = self.pull_file()
        if not success:
            messagebox.showerror(
                "Błąd komunikacji",
                f"Nie udało się pobrać pliku z gogli:\n{err}",
            )
            self.update_sinner_status_label()
            return

        self.config.read(LOCAL_INI, encoding="utf-8")
        section = "/Script/TWD.TWDGameUserSettings"

        if section in self.config and "bSinner" in self.config[section]:
            current_val = self.config[section]["bSinner"]
            new_val = "True" if current_val.lower() == "false" else "False"
            self.config[section]["bSinner"] = new_val

            backup_path = LOCAL_INI + ".bak"
            shutil.copyfile(LOCAL_INI, backup_path)

            with open(LOCAL_INI, "w", encoding="utf-8", newline="\n") as f:
                self.config.write(f)

            success_push, _ = self.push_file()
            if success_push:
                os.remove(backup_path)
                self.update_sinner_status_label()
                if self.settings_entries:
                    self.load_settings_into_gui()
            else:
                shutil.move(backup_path, LOCAL_INI)
                messagebox.showerror(
                    "Błąd zapisu", "Nie udało się wysłać pliku do gogli."
                )
                self.update_sinner_status_label()
        else:
            messagebox.showerror(
                "Błąd struktury",
                "W pobranym pliku nie znaleziono parametru bSinner.",
            )
            self.update_sinner_status_label()

    def update_sinner_status_label(self):
        if not os.path.exists(LOCAL_INI):
            self.lbl_sinner_status.config(
                text="Status: Brak pliku roboczego (użyj pobierania)",
                fg=TEXT_MUTED,
            )
            self.sinner_switch.set_state(False)
            return
        try:
            self.config.read(LOCAL_INI, encoding="utf-8")
            sec = "/Script/TWD.TWDGameUserSettings"
            if sec in self.config and "bSinner" in self.config[sec]:
                val = self.config[sec]["bSinner"]
                stan = "AKTYWNY" if val.lower() == "true" else "WYŁĄCZONY"
                color = ACCENT_PRIMARY if val.lower() == "true" else TEXT_MUTED
                self.lbl_sinner_status.config(
                    text=f"Status w pliku na goglach: {stan} (bSinner={val})",
                    fg=color,
                )
                self.sinner_switch.set_state(
                    val.lower() == "true", animate=True
                )
        except Exception:
            pass

    def load_settings_into_gui(self):
        success, err = self.pull_file()
        if not success:
            messagebox.showerror(
                "Błąd odczytu", f"Nie można pobrać pliku ustawień:\n{err}"
            )
            return

        self.config.read(LOCAL_INI, encoding="utf-8")

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.settings_entries.clear()

        for section in self.config.sections():
            card = tk.Frame(
                self.scroll_frame, bg=SURFACE_CONTAINER, padx=20, pady=16
            )
            card.pack(fill="x", pady=(0, 16), padx=(0, 8))

            lbl_sec = tk.Label(
                card,
                text=f"[{section}]",
                font=("Segoe UI", 12, "bold"),
                bg=SURFACE_CONTAINER,
                fg=ACCENT_PRIMARY,
            )
            lbl_sec.pack(anchor="w", pady=(0, 12))

            for key, val in self.config.items(section):
                row = tk.Frame(card, bg=SURFACE_CONTAINER)
                row.pack(fill="x", pady=4)

                lbl_k = tk.Label(
                    row,
                    text=key,
                    font=("Segoe UI", 10),
                    bg=SURFACE_CONTAINER,
                    fg=TEXT_MAIN,
                )
                lbl_k.pack(side="left")

                ent_v = tk.Entry(
                    row,
                    width=32,
                    font=("Consolas", 10),
                    bg=SURFACE_CONTAINER_HIGH,
                    fg=TEXT_MAIN,
                    insertbackground=ACCENT_PRIMARY,
                    relief="flat",
                    borderwidth=6,
                )
                ent_v.insert(0, val)
                ent_v.pack(side="right")

                self.settings_entries[(section, key)] = ent_v

        self.update_sinner_status_label()

    def save_settings_from_gui(self):
        if not self.settings_entries:
            messagebox.showwarning(
                "Brak danych", "Najpierw pobierz ustawienia z Questa!"
            )
            return

        for (section, key), entry_widget in self.settings_entries.items():
            self.config[section][key] = entry_widget.get()

        try:
            with open(LOCAL_INI, "w", encoding="utf-8", newline="\n") as f:
                self.config.write(f)

            success, err = self.push_file()
            if success:
                messagebox.showinfo(
                    "Sukces", "Modyfikacja zapisana wewnątrz gogli!"
                )
            else:
                messagebox.showerror(
                    "Błąd ADB",
                    f"Nie udało się nadpisać pliku w goglach:\n{err}",
                )
        except Exception as e:
            messagebox.showerror(
                "Błąd zapisu", f"Problem z plikiem roboczym:\n{str(e)}"
            )


if __name__ == "__main__":
    app = TWDMaterialModder()
    app.mainloop()