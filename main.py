#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testify v2.3.0 — FULL
Hey there! This is a modern ISEE-style runner thingy:
- Light/Dark/High-contrast themes (accent = (42,148,158)), looks pretty chill
- Header logo if you got assets/menu_logo.png; if not, just "Testify" text (no ugly placeholder tho)
- Taskbar/Dock icon: tries app_icon_1080.png, then app_icon_1024.png, then app_icon.png; if none, goes transparent so you don't get the pygame logo (ew)
- Buttons have hover/pressed states, and click is on mouse-up inside the button (feels better, trust me)
- Exam & Practice modes (pill toggle); Practice mode lets you "Skip to Next Section" if there's time left or it's untimed
- Section Lobby, Section screen w/ choices, keyboard shortcuts, timer, the works
- Results screen lets you save TXT or export JSON
- You can drag-and-drop .json files anywhere to load 'em
- Toasts are animated: slide up, hang for 4s, slide down; only show for big stuff (load/save/export); you can click to dismiss
- Exam Builder: make/edit sections/items; Save As... uses native dialog if possible, or falls back to a regular save
- No placeholders in code, for real (I hate those)
"""

import os
import sys
import json
import datetime

#
# --- EARLY crash logger (has to go before pygame import or stuff blows up) ---
def _user_data_dir_early():
    try:
        if sys.platform == "darwin":
            p = os.path.expanduser("~/Library/Application Support/Testify")
        elif sys.platform.startswith("win"):
            p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Testify")
        else:
            p = os.path.expanduser("~/.local/share/testify")
        os.makedirs(p, exist_ok=True)
        return p
    except Exception:
        return os.getcwd()

def _install_crash_logger_early():
    log_path = os.path.join(_user_data_dir_early(), "testify_crash.log")
    def _hook(exc_type, exc, tb):
        try:
            import traceback, datetime as _dt
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n===== Early Crash @ %s =====\n" % _dt.datetime.now().isoformat(timespec="seconds"))
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
    sys.excepthook = _hook

def _early_log(msg):
    try:
        lp = os.path.join(_user_data_dir_early(), "testify_crash.log")
        with open(lp, "a", encoding="utf-8") as f:
            import datetime as _dt
            f.write("[%s] %s\n" % (_dt.datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass

_install_crash_logger_early()

#
# Try importing pygame (or pygame-ce) with error capture (so it doesn't just explode on import)
try:
    import pygame  # standard package
except Exception as _pg_ex_primary:
    try:
        import pygame_ce as pygame  # fallback to pygame-ce
        _early_log("Using pygame-ce fallback")
    except Exception as _pg_ex_secondary:
        # log both errors (because why not)
        _early_log(f"pygame import failed: {getattr(_pg_ex_primary, 'args', _pg_ex_primary)}")
        _early_log(f"pygame_ce import failed: {getattr(_pg_ex_secondary, 'args', _pg_ex_secondary)}")
        if sys.platform == "darwin":
            try:
                safe_msg = f"{_pg_ex_primary}".replace('"', '\\"')
                safe_msg2 = f"{_pg_ex_secondary}".replace('"', '\\"')
                os.system(
                    f'''osascript -e 'display alert "Testify failed to start" message "Neither pygame nor pygame-ce could be imported.\npygame: {safe_msg}\npygame-ce: {safe_msg2}"' '''
                )
            except Exception:
                pass
        raise


#
# ---------- Lazy Tk initialization (this is to avoid weird mac .app launch bugs) ----------
_TK_OK = False
_TK_ROOT = None
_TK_IMPORTED = False
try:
    import tkinter as _tk
    from tkinter import filedialog as _fd
    _TK_IMPORTED = True
except Exception:
    _TK_IMPORTED = False

def _ensure_tk_root():
    """Make one hidden Tk root on first use; safe in frozen apps. (Yeah, Tk is kinda annoying)"""
    global _TK_OK, _TK_ROOT
    if not _TK_IMPORTED:
        _TK_OK = False
        _TK_ROOT = None
        return False
    if _TK_ROOT is not None:
        return _TK_OK
    try:
        _TK_ROOT = _tk.Tk()
        _TK_ROOT.withdraw()
        _TK_OK = True
    except Exception:
        _TK_ROOT = None
        _TK_OK = False
    return _TK_OK


APP_NAME = "Testify"
VERSION = "2.3.1"
ACCENT_BLUE = (42, 148, 158)

#
# ---------------------------- Settings ----------------------------
def _base_dir():
    """
    Returns the base dir for bundled assets.
    - If running as a frozen PyInstaller app, it's sys._MEIPASS.
    - Otherwise just the folder this file lives in.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))

#
# Helper to get a per-user writable data dir (so we don't mess up system files)
def _user_data_dir():
    """
    Returns a writable per-user data directory and makes sure it exists.
    macOS: ~/Library/Application Support/Testify
    Windows: %APPDATA%/Testify
    Linux: ~/.local/share/testify
    """
    try:
        if sys.platform == "darwin":
            p = os.path.expanduser("~/Library/Application Support/Testify")
        elif sys.platform.startswith("win"):
            p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Testify")
        else:
            p = os.path.expanduser("~/.local/share/testify")
        os.makedirs(p, exist_ok=True)
        return p
    except Exception:
        # Ultimate fallback to current working directory
        return os.getcwd()

#
# Re-point excepthook to user-data path (uses same early hook pattern as above)
def _install_crash_logger():
    log_path = os.path.join(_user_data_dir(), "testify_crash.log")
    def _hook(exc_type, exc, tb):
        try:
            import traceback
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n===== Crash @ %s =====\n" % datetime.datetime.now().isoformat(timespec="seconds"))
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
    sys.excepthook = _hook

_install_crash_logger()

#
# --------- Small runtime logging helper ---------
def _log_runtime(msg):
    try:
        lp = os.path.join(_user_data_dir(), "testify_crash.log")
        with open(lp, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass

def _settings_path():
    return os.path.join(_user_data_dir(), "isee_runner_settings.json")

DEFAULT_SETTINGS = {
    "theme": "light",          # can be: light | dark | high_contrast
    "mode": "exam",            # exam | practice
    "goal_overall": 85,        # not really used, but hey
    "goal_per_section": 80,    # ditto
    "font_size": 24            # default font size, tweak if you like big text
}

def load_settings():
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            s = json.load(f)
        for k,v in DEFAULT_SETTINGS.items():
            s.setdefault(k, v)
        return s
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(s):
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print("Could not save settings:", ex)

#
# ---------------------------- Themes ----------------------------
THEMES = {
    "light": {
        "bg": (246,248,250),
        "panel": (255,255,255),
        "text": (24,24,28),
        "muted": (110,110,118),
        "accent": ACCENT_BLUE,
        "ok": (16,185,129),
        "warn": (255,186,73),
        "bad": (239,68,68),
        "shadow": (0,0,0,36),
        "chip": (245,247,255)
    },
    "dark": {
        "bg": (22,24,28),
        "panel": (33,36,41),
        "text": (235,235,240),
        "muted": (165,168,178),
        "accent": ACCENT_BLUE,
        "ok": (52,211,153),
        "warn": (250,204,21),
        "bad": (248,113,113),
        "shadow": (0,0,0,60),
        "chip": (44,47,54)
    },
    "high_contrast": {
        "bg": (0,0,0),
        "panel": (255,255,255),
        "text": (0,0,0),
        "muted": (32,32,32),
        "accent": ACCENT_BLUE,
        "ok": (0,180,0),
        "warn": (255,160,0),
        "bad": (220,0,0),
        "shadow": (255,255,255,90),
        "chip": (240,240,240)
    }
}

#
# ---------------------------- Assets & Icons ----------------------------
def load_img(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None

def load_app_logo():
    p = os.path.join(_base_dir(), "assets", "menu_logo.png")
    return load_img(p)

def load_app_taskbar_icon():
    base = _base_dir()
    for fname in ("app_icon_1080.png", "app_icon_1024.png", "app_icon.png"):
        p = os.path.join(base, "assets", fname)
        img = load_img(p)
        if img:
            return img
    return None

def set_window_icon():
    icon = load_app_taskbar_icon()
    # Always set the window/taskbar icon for Win/Linux (and window titlebar on macOS)
    if icon:
        surf = pygame.transform.smoothscale(icon, (64,64))
        pygame.display.set_icon(surf)
    else:
        # transparent to avoid pygame logo (otherwise you get that ugly snake)
        blank = pygame.Surface((32,32), pygame.SRCALPHA)
        blank.fill((0,0,0,0))
        pygame.display.set_icon(blank)

    # Extra step for macOS Dock icon (needs PyObjC, but it's fine if not installed)
    if sys.platform == "darwin":
        try:
            from Cocoa import NSApplication, NSImage  # type: ignore
            # pick the best icon file we actually have
            p = None
            for fname in ("app_icon_1080.png", "app_icon_1024.png", "app_icon.png"):
                candidate = os.path.join(_base_dir(), "assets", fname)
                if os.path.isfile(candidate):
                    p = candidate
                    break
            if p:
                img = NSImage.alloc().initWithContentsOfFile_(p)
                if img:
                    NSApplication.sharedApplication().setApplicationIconImage_(img)
        except Exception:
            # If Cocoa/PyObjC isn't present, ignore — .icns will still show the right Dock icon if you package as .app anyway
            pass

def load_icon(name, size):
    """Load an icon PNG from assets/icons. If it's missing, just returns None (no placeholder, sorry)"""
    p = os.path.join(_base_dir(), "assets", "icons", f"{name}.png")
    img = load_img(p)
    if not img:
        return None
    return pygame.transform.smoothscale(img, (size,size)).convert_alpha()

#
# ---------------------------- Fonts & Helpers ----------------------------
def mk_fonts(base_size, custom_path=None):
    try:
        if custom_path and os.path.isfile(custom_path):
            return {
                "body": pygame.font.Font(custom_path, base_size),
                "bold": pygame.font.Font(custom_path, base_size),
                "h1": pygame.font.Font(custom_path, int(base_size*1.8)),
                "mono": pygame.font.Font(custom_path, max(14, base_size-2))
            }
    except Exception:
        pass
    mono_name = (pygame.font.match_font("menlo") or
                 pygame.font.match_font("consolas") or
                 pygame.font.match_font("courier new"))
    return {
        "body": pygame.font.SysFont(None, base_size),
        "bold": pygame.font.SysFont(None, base_size, bold=True),
        "h1": pygame.font.SysFont(None, int(base_size*1.8), bold=True),
        "mono": (pygame.font.Font(mono_name, max(14, base_size-2)) if mono_name
                 else pygame.font.SysFont(None, max(14, base_size-2)))
    }

def draw_text(s, font, color):
    return font.render(s, True, color)

def blit_shadowed_card(screen, rect, theme):
    shadow = pygame.Surface((rect.width+20, rect.height+20), pygame.SRCALPHA)
    pygame.draw.rect(shadow, theme["shadow"], shadow.get_rect(), border_radius=20)
    screen.blit(shadow, (rect.x-10, rect.y-6))
    pygame.draw.rect(screen, theme["panel"], rect, border_radius=16)

def draw_chip(surf, rect, theme):
    pygame.draw.rect(surf, theme["chip"], rect, border_radius=12)

#
# ---------- Responsive button row layout ----------
def layout_button_row(container_rect, buttons, theme, fonts, align="center", pad_x=16, pad_y=12, gap=12, min_w=120, max_w=220, h=44):
    """
    Lay out buttons in a single row at the bottom of container_rect.
    - buttons: list[Button] (their rects get reassigned here)
    - align: 'center' | 'left' | 'right'
    This also draws the buttons after placing 'em.
    """
    n = len(buttons)
    if n == 0: return
    avail_w = container_rect.width - pad_x*2
    # pick width that fits, clamped
    w = min(max_w, max(min_w, int((avail_w - gap*(n-1)) / n)))
    # if still doesn't fit, reduce gap to at least 6 and recompute
    if w*n + gap*(n-1) > avail_w:
        gap_eff = max(6, avail_w - w*n) // max(1, (n-1))
    else:
        gap_eff = gap
    row_w = w*n + gap_eff*(n-1)
    if align == "left":
        start_x = container_rect.left + pad_x
    elif align == "right":
        start_x = container_rect.right - pad_x - row_w
    else:  # center
        start_x = container_rect.left + (container_rect.width - row_w)//2
    y = container_rect.bottom - pad_y - h
    x = start_x
    for b in buttons:
        b.rect = pygame.Rect(int(x), int(y), int(w), int(h))
        b.draw(pygame.display.get_surface(), theme, fonts)
        x += w + gap_eff

_wrap_cache = {}
def wrap_lines(s, font, width):
    # Word wrap helper, but with a tiny cache so it doesn't get slow
    key = (s, font.get_height(), width)
    if key in _wrap_cache: return _wrap_cache[key]
    words = s.split()
    out, cur = [], ""
    for w in words:
        t = w if not cur else cur+" "+w
        if font.size(t)[0] <= width:
            cur = t
        else:
            if cur: out.append(cur)
            cur = w
    if cur: out.append(cur)
    _wrap_cache[key] = out
    return out

#
# ---------------------------- Widgets ----------------------------
class Button:
    def __init__(self, rect, label, icon=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.icon = icon
        self.enabled = True
        self.hover = False
        self.pressed = False

    def handle_event(self, e):
        if not self.enabled: return False
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
            return False
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            return self.rect.collidepoint(e.pos)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.pressed = True
        return False

    def draw(self, surf, theme, fonts):
        base = theme["accent"] if self.enabled else (160,160,170)
        bg = base
        if self.pressed: bg = (int(base[0]*0.8), int(base[1]*0.8), int(base[2]*0.8))
        elif self.hover: bg = (int(base[0]*0.9), int(base[1]*0.9), int(base[2]*0.9))
        pygame.draw.rect(surf, bg, self.rect, border_radius=12)
        pygame.draw.rect(surf, (255,255,255,28), self.rect.inflate(-6,-6), 1, border_radius=10)

        y = self.rect.centery
        icon_surf = load_icon(self.icon, 22) if self.icon else None
        if icon_surf is not None:
            ir = icon_surf.get_rect()
            ir.centery = y
            ir.x = self.rect.x + 14
            surf.blit(icon_surf, ir.topleft)
            lab = draw_text(self.label, fonts["bold"], (255,255,255))
            tr = lab.get_rect(); tr.centery = y; tr.x = ir.right + 8
            surf.blit(lab, tr.topleft)
        else:
            lab = draw_text(self.label, fonts["bold"], (255,255,255))
            surf.blit(lab, lab.get_rect(center=self.rect.center))

class PillToggle:
    def __init__(self, rect, left_label, right_label):
        self.rect = pygame.Rect(rect)
        self.left_label = left_label
        self.right_label = right_label
        self.value = 0
    def draw(self, surf, theme, fonts):
        pygame.draw.rect(surf, theme["chip"], self.rect, border_radius=20)
        knob = pygame.Rect(self.rect.x+4 + (self.rect.width//2 if self.value else 0),
                           self.rect.y+4, self.rect.width//2-8, self.rect.height-8)
        pygame.draw.rect(surf, theme["accent"], knob, border_radius=16)
        left = draw_text(self.left_label, fonts["bold"], theme["text"])
        right = draw_text(self.right_label, fonts["bold"], theme["text"])
        surf.blit(left, (self.rect.x+14, self.rect.y + (self.rect.height-left.get_height())//2))
        surf.blit(right, (self.rect.x + self.rect.width//2 + 14, self.rect.y + (self.rect.height-right.get_height())//2))
    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.rect.collidepoint(e.pos):
            self.value = 1 - self.value
            return True
        return False

class TextInput:
    def __init__(self, rect, text="", multiline=False, numeric=False, placeholder=""):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.multiline = multiline
        self.numeric = numeric
        self.placeholder = placeholder
        self.active = False
        self.cursor = len(text)
        self.last_blink = 0
        self.show_cursor = True
    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)
            return False
        if self.active and e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                if self.cursor>0:
                    self.text = self.text[:self.cursor-1]+self.text[self.cursor:]
                    self.cursor -= 1
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.multiline:
                    self.text = self.text[:self.cursor] + "\n" + self.text[self.cursor:]
                    self.cursor += 1
            elif e.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor-1)
            elif e.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor+1)
            elif e.unicode:
                if self.numeric and not (e.unicode.isdigit() or e.unicode in "-"):
                    return False
                self.text = self.text[:self.cursor] + e.unicode + self.text[self.cursor:]
                self.cursor += 1
        return False
    def draw(self, surf, fonts, theme):
        pygame.draw.rect(surf, theme["chip"], self.rect, border_radius=10)
        txt = self.text if self.text else self.placeholder
        color = theme["text"] if self.text else theme["muted"]
        if self.multiline:
            y = self.rect.y + 6
            for line in txt.split("\n") or [""]:
                img = draw_text(line, fonts["body"], color)
                surf.blit(img, (self.rect.x+8, y)); y += img.get_height()+4
        else:
            img = draw_text(txt, fonts["body"], color)
            surf.blit(img, (self.rect.x+8, self.rect.y + (self.rect.height-img.get_height())//2))
        if self.active:
            now = pygame.time.get_ticks()
            if now - self.last_blink > 500:
                self.show_cursor = not self.show_cursor; self.last_blink = now
            if self.show_cursor:
                before = self.text[:self.cursor].split("\n")[-1] if self.multiline else self.text[:self.cursor]
                cx = fonts["body"].size(before)[0]
                cy = fonts["body"].get_height()
                x = self.rect.x + 8 + cx
                y = self.rect.y + 6 if self.multiline else self.rect.y + (self.rect.height-cy)//2
                pygame.draw.line(surf, theme["text"], (x, y), (x, y+cy), 1)

#
# ---------------------------- Exam IO ----------------------------
def parse_exam(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as ex:
        raise ValueError(f"Invalid JSON: {ex}")
    if not isinstance(data, dict) or "sections" not in data:
        raise ValueError("JSON must have a top-level 'sections' array.")
    sections = []
    for sec in data["sections"]:
        name = sec.get("name","Untitled")
        items = sec.get("items",[])
        tmin = sec.get("time_minutes")
        for it in items:
            it.setdefault("q",""); it.setdefault("choices",[]); it.setdefault("ans",""); it.setdefault("passage","")
        sections.append([name, items, tmin])
    return sections

#
# ---------------------------- Toast ----------------------------
class Toast:
    def __init__(self):
        self.msg = ""
        self.phase = "idle"
        self.ts = 0
        self.in_ms = 180; self.hold_ms = 4000; self.out_ms = 200
        self.rect = None
    def trigger(self, msg):
        self.msg = msg or ""
        if not self.msg: self.phase="idle"; return
        self.phase = "in"; self.ts = pygame.time.get_ticks()
    def draw(self, screen, fonts, theme, H):
        if not self.msg or self.phase=="idle":
            self.rect=None; return
        now = pygame.time.get_ticks(); elapsed = now - self.ts
        y_off = 0
        if self.phase=="in":
            t=min(1, elapsed/self.in_ms); y_off = int((1-t)*50)
            if t>=1: self.phase="hold"; self.ts=now
        elif self.phase=="hold":
            if elapsed>=self.hold_ms: self.phase="out"; self.ts=now
        elif self.phase=="out":
            t=min(1, elapsed/self.out_ms); y_off = int(t*50)
            if t>=1: self.phase="idle"; self.msg=""; self.rect=None; return
        r = pygame.Rect(20, H-56 + y_off, screen.get_width()-40, 36)
        self.rect=r
        blit_shadowed_card(screen, r, theme)
        screen.blit(draw_text(self.msg[-200:], fonts["body"], theme["muted"]), (r.left+12, r.top+7))

#
# ---------------------------- States ----------------------------
S_HOME, S_SETTINGS, S_HELP, S_LOBBY, S_SECTION, S_RESULTS, S_BUILDER = range(7)

#
# ---------------------------- App ----------------------------
class App:
    def __init__(self, initial_json=None):
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} v{VERSION}")
        set_window_icon()  # pre-set (some platforms read this prior to set_mode)
        self.W, self.H = 1200, 780
        self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)
        set_window_icon()  # post-set (mac/win variants sometimes require after set_mode too)
        self.clock = pygame.time.Clock()

        self.settings = load_settings()
        self.theme = THEMES.get(self.settings.get("theme","light"), THEMES["light"])
        self.fonts = mk_fonts(self.settings.get("font_size",24),
                              os.path.join(_base_dir(), "ui_font.ttf"))
        self.menu_logo = load_app_logo()

        # exam
        self.exam_path = initial_json if initial_json and os.path.isfile(initial_json) else None
        self.sections_all = []
        self.state = S_HOME
        if self.exam_path:
            try:
                self.sections_all = parse_exam(self.exam_path)
            except Exception as ex:
                print("Load error:", ex)

        # runtime
        self.toast = Toast()
        self.sec_i = 0; self.q_i = 0
        self.answers = {}
        self.locked = {}
        self.time_left_ms = None; self.last_tick = pygame.time.get_ticks()
        self.results = None

        # builder
        self.builder_sections = []
        self.b_sel_sec = -1
        self.b_sel_item = -1
        self._init_builder_inputs()

    # ---------- builder inputs (for Exam Builder screen) ----------
    def _init_builder_inputs(self):
        self.in_sec_name = TextInput(pygame.Rect(0,0,0,0), "", placeholder="Section name")
        self.in_time = TextInput(pygame.Rect(0,0,0,0), "", numeric=True, placeholder="Time (minutes) or blank")
        self.in_q = TextInput(pygame.Rect(0,0,0,0), "", multiline=True, placeholder="Question")
        self.in_passage = TextInput(pygame.Rect(0,0,0,0), "", multiline=True, placeholder="Passage (optional)")
        self.in_choice = [TextInput(pygame.Rect(0,0,0,0), "", placeholder=f"Choice {c}") for c in "ABCD"]
        self.in_ans = TextInput(pygame.Rect(0,0,0,0), "", placeholder="Correct (A/B/C/D)")

    def _sync_inputs_from_model(self):
        if 0 <= self.b_sel_sec < len(self.builder_sections):
            sec = self.builder_sections[self.b_sel_sec]
            self.in_sec_name.text = sec.get("name","")
            tm = sec.get("time_minutes", None)
            self.in_time.text = "" if tm in (None, "") else str(tm)
            if 0 <= self.b_sel_item < len(sec.get("items",[])):
                it = sec["items"][self.b_sel_item]
                self.in_q.text = it.get("q","")
                self.in_passage.text = it.get("passage","")
                ch = it.get("choices", [])
                for i in range(4):
                    self.in_choice[i].text = ch[i] if i < len(ch) else ""
                self.in_ans.text = it.get("ans","")
            else:
                self.in_q.text = ""
                self.in_passage.text = ""
                for i in range(4): self.in_choice[i].text = ""
                self.in_ans.text = ""
        else:
            self.in_sec_name.text = ""
            self.in_time.text = ""
            self.in_q.text = ""
            self.in_passage.text = ""
            for i in range(4): self.in_choice[i].text = ""
            self.in_ans.text = ""

    def _apply_inputs_to_model(self):
        if 0 <= self.b_sel_sec < len(self.builder_sections):
            sec = self.builder_sections[self.b_sel_sec]
            sec["name"] = self.in_sec_name.text.strip() or "Untitled"
            # time
            ttxt = self.in_time.text.strip()
            if ttxt == "": sec["time_minutes"] = None
            else:
                try: sec["time_minutes"] = int(ttxt)
                except: sec["time_minutes"] = None
            # item
            if 0 <= self.b_sel_item < len(sec.get("items",[])):
                it = sec["items"][self.b_sel_item]
                it["q"] = self.in_q.text.strip()
                it["passage"] = self.in_passage.text
                it["choices"] = [c.text.strip() for c in self.in_choice if c.text.strip()!=""]
                it["ans"] = (self.in_ans.text.strip().upper()[:1] if self.in_ans.text.strip() else "")

    # ---------- utils (mostly resizing/font stuff) ----------
    def on_resize(self, w, h):
        self.screen = pygame.display.set_mode((max(1000, w), max(640, h)), pygame.RESIZABLE)
        self.W, self.H = self.screen.get_size()
        base = 22 if self.W < 1100 else 24 if self.W < 1400 else 26
        self.fonts = mk_fonts(base, os.path.join(_base_dir(), "ui_font.ttf"))

    def fill_bg(self):
        self.screen.fill(self.theme["bg"])

    def header(self):
        bar = pygame.Rect(0,0,self.W,72)
        blit_shadowed_card(self.screen, bar, self.theme)
        if self.menu_logo:
            h = 56
            w = int(self.menu_logo.get_width() * (h / self.menu_logo.get_height()))
            lg = pygame.transform.smoothscale(self.menu_logo,(w,h))
            self.screen.blit(lg, (18,8))
        else:
            self.screen.blit(draw_text(APP_NAME, self.fonts["h1"], self.theme["text"]), (20,14))
        ver = draw_text(f"v{VERSION}", self.fonts["body"], self.theme["muted"])
        self.screen.blit(ver, (self.W-ver.get_width()-18, 24))

    # ---------- toast (for little notification popups) ----------
    def draw_toast(self):
        self.toast.draw(self.screen, self.fonts, self.theme, self.H)

    # ---------- screens (all the different UI pages) ----------
    def scr_home(self, events):
        self.fill_bg(); self.header()
        card = pygame.Rect(int(self.W*0.1), 100, int(self.W*0.8), self.H-160)
        blit_shadowed_card(self.screen, card, self.theme)

        y = card.top+22
        self.screen.blit(draw_text("Welcome", self.fonts["h1"], self.theme["text"]), (card.left+20, y)); y+=56
        for ln in [
            "Drag & drop a .json exam file here, or pass it as a command-line argument.",
            "Use Settings to switch Theme and Mode (Exam or Practice).",
            "Build an exam with the Exam Builder.",
            "Tip: A/B/C/D to answer, ←/→ to move, Enter to submit, Esc to Lobby (Practice)."
        ]:
            for w in wrap_lines(ln, self.fonts["body"], card.width-40):
                self.screen.blit(draw_text(w, self.fonts["body"], self.theme["muted"]), (card.left+20, y)); y+=28
        y += 10
        self.screen.blit(draw_text(f"Loaded file: {os.path.basename(self.exam_path) if self.exam_path else '(none)'}", self.fonts["body"], self.theme["text"]), (card.left+20, y)); y+=40

        self.btn_start = Button(pygame.Rect(0,0,0,0), "Start", icon="play")
        self.btn_settings = Button(pygame.Rect(0,0,0,0), "Settings", icon="settings")
        self.btn_builder = Button(pygame.Rect(0,0,0,0), "Exam Builder", icon="code")
        self.btn_help = Button(pygame.Rect(0,0,0,0), "Help", icon="help")
        self.btn_quit = Button(pygame.Rect(0,0,0,0), "Quit", icon="power")
        self.btn_start.enabled = bool(self.sections_all)

        layout_button_row(card, [self.btn_start, self.btn_settings, self.btn_builder, self.btn_help, self.btn_quit],
                          self.theme, self.fonts, align="center", pad_x=20, pad_y=20, gap=12, min_w=120, max_w=220, h=44)

        for e in events:
            if self.btn_start.handle_event(e): self.state = S_LOBBY
            elif self.btn_settings.handle_event(e): self.state = S_SETTINGS
            elif self.btn_builder.handle_event(e):
                self.builder_sections = [] ; self.b_sel_sec = -1 ; self.b_sel_item = -1
                self._sync_inputs_from_model()
                self.state = S_BUILDER
            elif self.btn_help.handle_event(e): self.state = S_HELP
            elif self.btn_quit.handle_event(e): pygame.event.post(pygame.event.Event(pygame.QUIT))
            elif e.type == pygame.DROPFILE:
                try:
                    p = e.file
                    self.sections_all = parse_exam(p); self.exam_path = p
                    self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex:
                    self.toast.trigger(f"Load error: {ex}")
        self.draw_toast()

    def scr_settings(self, events):
        self.fill_bg(); self.header()
        card = pygame.Rect(int(self.W*0.1), 100, int(self.W*0.8), self.H-160)
        blit_shadowed_card(self.screen, card, self.theme)

        y = card.top+20
        self.screen.blit(draw_text("Settings", self.fonts["h1"], self.theme["text"]), (card.left+20, y)); y+=56

        # Theme chips
        self.screen.blit(draw_text("Theme", self.fonts["bold"], self.theme["text"]), (card.left+20, y)); y+=36
        themes = ["light","dark","high_contrast"]; self.theme_buttons=[]
        bx = card.left+20
        for nm in themes:
            r = pygame.Rect(bx, y, 180, 40); bx += 196
            draw_chip(self.screen, r, self.theme)
            active = (self.settings.get("theme","light")==nm)
            if active: pygame.draw.rect(self.screen, self.theme["ok"], r, 3, border_radius=12)
            icon = load_icon(nm, 22)
            if icon: self.screen.blit(icon, (r.x+10, r.y+9))
            self.screen.blit(draw_text(nm.replace("_"," ").title(), self.fonts["body"], self.theme["text"]), (r.x+40, r.y+9))
            self.theme_buttons.append((nm, r))
        y+=60

        # Mode pill toggle
        self.screen.blit(draw_text("Mode", self.fonts["bold"], self.theme["text"]), (card.left+20, y)); y+=36
        self.mode_toggle = PillToggle((card.left+20, y, 300, 44), "Exam", "Practice")
        self.mode_toggle.value = 0 if self.settings.get("mode","exam")=="exam" else 1
        self.mode_toggle.draw(self.screen, self.theme, self.fonts)
        y+=70

        # font size
        self.screen.blit(draw_text("Font size", self.fonts["bold"], self.theme["text"]), (card.left+20, y))
        cur = str(self.settings.get("font_size",24))
        self.screen.blit(draw_text(cur, self.fonts["body"], self.theme["muted"]), (card.left+120, y))
        self.btn_fm = Button((card.left+180, y-6, 40,40), "–")
        self.btn_fp = Button((card.left+230, y-6, 40,40), "+")
        self.btn_fm.draw(self.screen, self.theme, self.fonts)
        self.btn_fp.draw(self.screen, self.theme, self.fonts)
        y+=64
        self.btn_back = Button(pygame.Rect(0,0,0,0), "Back", icon="back")
        layout_button_row(card, [self.btn_back], self.theme, self.fonts, align="left", pad_x=20, pad_y=20, gap=12, min_w=140, max_w=180, h=44)

        for e in events:
            if e.type == pygame.MOUSEBUTTONUP and e.button==1:
                for nm, r in self.theme_buttons:
                    if r.collidepoint(e.pos):
                        self.settings["theme"]=nm; save_settings(self.settings)
                        self.theme = THEMES[nm]  # apply immediately
                        self.fill_bg()
            if self.mode_toggle.handle_event(e):
                self.settings["mode"] = "practice" if self.mode_toggle.value==1 else "exam"
                save_settings(self.settings)
            if self.btn_fm.handle_event(e):
                self.settings["font_size"]=max(18,self.settings.get("font_size",24)-2); save_settings(self.settings)
                self.fonts = mk_fonts(self.settings["font_size"], os.path.join(_base_dir(), "ui_font.ttf"))
            if self.btn_fp.handle_event(e):
                self.settings["font_size"]=min(32,self.settings.get("font_size",24)+2); save_settings(self.settings)
                self.fonts = mk_fonts(self.settings["font_size"], os.path.join(_base_dir(), "ui_font.ttf"))
            if self.btn_back.handle_event(e):
                self.state = S_HOME
            elif e.type == pygame.DROPFILE:
                try:
                    p=e.file; self.sections_all=parse_exam(p); self.exam_path=p; self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex: self.toast.trigger(f"Load error: {ex}")
        self.draw_toast()

    def scr_help(self, events):
        self.fill_bg(); self.header()
        card = pygame.Rect(int(self.W*0.1), 100, int(self.W*0.8), self.H-160)
        blit_shadowed_card(self.screen, card, self.theme)
        y = card.top+20
        self.screen.blit(draw_text("Help", self.fonts["h1"], self.theme["text"]), (card.left+20, y)); y+=56
        for ln in [
            "Load JSON: Drag & drop onto any screen or pass a file path when launching.",
            "Controls: A/B/C/D to answer; ←/→ to move; Enter to submit; Esc to Lobby (Practice).",
            "Exam Mode: Timer locks sections; Practice Mode lets you roam. Skip button appears in Practice.",
            "Results: Save TXT or Export JSON with your performance.",
            "Exam Builder: Create sections/items and Save As JSON (Testify format)."
        ]:
            for w in wrap_lines(ln, self.fonts["body"], card.width-40):
                self.screen.blit(draw_text(w, self.fonts["body"], self.theme["muted"]), (card.left+20,y)); y+=28
        self.btn_back = Button(pygame.Rect(0,0,0,0), "Back", icon="back")
        layout_button_row(card, [self.btn_back], self.theme, self.fonts, align="left", pad_x=20, pad_y=20, gap=12, min_w=140, max_w=180, h=44)
        for e in events:
            if self.btn_back.handle_event(e):
                self.state = S_HOME
            elif e.type == pygame.DROPFILE:
                try:
                    p=e.file; self.sections_all=parse_exam(p); self.exam_path=p; self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex: self.toast.trigger(f"Load error: {ex}")
        self.draw_toast()

    def scr_lobby(self, events):
        self.fill_bg(); self.header()
        card = pygame.Rect(int(self.W*0.06), 90, int(self.W*0.88), self.H-140)
        blit_shadowed_card(self.screen, card, self.theme)
        y = card.top+16
        self.screen.blit(draw_text("Section Lobby", self.fonts["h1"], self.theme["text"]), (card.left+20, y)); y+=46
        mode = self.settings.get("mode","exam")
        self.screen.blit(draw_text(f"Mode: {mode.capitalize()} • File: {os.path.basename(self.exam_path) if self.exam_path else '(none)'}", self.fonts["body"], self.theme["muted"]), (card.left+20, y)); y+=36

        self.section_buttons=[]
        by=y
        for i,(name,items,tmin) in enumerate(self.sections_all):
            locked = self.locked.get(name, False) and mode=="exam"
            label = f"{i+1}. {name}   ({tmin if tmin else 'untimed'} min)   • {len(items)} items"
            if locked: label += "   — LOCKED"
            btn = Button((card.left+20, by, card.width-40, 56), label, icon=("lock" if locked else "section"))
            btn.enabled = not locked
            self.section_buttons.append((i,btn)); btn.draw(self.screen, self.theme, self.fonts); by+=64

        self.btn_home = Button(pygame.Rect(0,0,0,0), "Home", icon="home")
        self.btn_results = Button(pygame.Rect(0,0,0,0), "View Results", icon="chart")
        self.btn_results.enabled = bool(self.results)
        layout_button_row(card, [self.btn_home, self.btn_results], self.theme, self.fonts, align="left", pad_x=20, pad_y=20, gap=12, min_w=150, max_w=220, h=44)

        for e in events:
            if self.btn_home.handle_event(e): self.state = S_HOME
            elif self.btn_results.handle_event(e): self.state = S_RESULTS
            elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                pass
            elif e.type == pygame.DROPFILE:
                try:
                    p=e.file; self.sections_all=parse_exam(p); self.exam_path=p; self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex: self.toast.trigger(f"Load error: {ex}")
            else:
                for idx, b in self.section_buttons:
                    if b.handle_event(e):
                        name = self.sections_all[idx][0]
                        if self.locked.get(name, False) and mode=="exam":
                            pass
                        else:
                            self.start_section(idx)
        self.draw_toast()

    def start_section(self, idx):
        self.sec_i = idx; name, items, tmin = self.sections_all[idx]
        if name not in self.answers: self.answers[name] = [None]*len(items)
        if name not in self.locked: self.locked[name] = False
        self.q_i = 0; self.last_tick = pygame.time.get_ticks()
        self.time_left_ms = int((tmin or 0)*60_000) if tmin else None
        self.state = S_SECTION

    def tick_timer(self):
        if self.time_left_ms is None: return
        now = pygame.time.get_ticks(); delta = now - self.last_tick; self.last_tick = now
        if self.settings.get("mode","exam") == "exam":
            self.time_left_ms = max(0, self.time_left_ms - delta)
            if self.time_left_ms == 0:
                name,_,_=self.sections_all[self.sec_i]; self.locked[name]=True
                self.toast.trigger("Time’s up — advancing…")
                if self.sec_i < len(self.sections_all)-1: self.start_section(self.sec_i+1)
                else: self.finish_exam()

    def scr_section(self, events):
        self.fill_bg(); self.header()
        name, items, tmin = self.sections_all[self.sec_i]
        item = items[self.q_i]; total = len(items)
        is_exam = (self.settings.get("mode","exam") == "exam")

        left = pygame.Rect(20, 90, int(self.W*0.6-30), self.H-120)
        right = pygame.Rect(int(self.W*0.6+10), 90, int(self.W*0.4-30), self.H-120)
        blit_shadowed_card(self.screen, left, self.theme); blit_shadowed_card(self.screen, right, self.theme)

        # header on left
        title = f"{name} — Q {self.q_i+1}/{total}"
        self.screen.blit(draw_text(title, self.fonts["bold"], self.theme["text"]), (left.left+16, left.top+12))

        # timer
        if self.time_left_ms is not None:
            mins = self.time_left_ms//60000; secs = (self.time_left_ms%60000)//1000
            col = self.theme["bad"] if mins<1 else (self.theme["warn"] if mins<5 else self.theme["muted"])
            chip = pygame.Rect(right.left+16, right.top+12, 220, 30); draw_chip(self.screen, chip, self.theme)
            self.screen.blit(draw_text(f"Time left: {mins:02d}:{secs:02d}", self.fonts["bold"], col), (chip.x+10, chip.y+5))

        # Skip button (Practice mode)
        next_exists = self.sec_i < len(self.sections_all)-1
        skip_enabled = (not is_exam) and next_exists and (self.time_left_ms is None or self.time_left_ms > 0)
        if next_exists:
            self.btn_skip = Button((right.left+16, right.bottom-56, 220,40), "Skip to Next Section", icon="chev_right")
            self.btn_skip.enabled = skip_enabled
            self.btn_skip.draw(self.screen, self.theme, self.fonts)
        else:
            self.btn_skip = None

        # passage on right
        py = right.top+50
        if item.get("passage"):
            self.screen.blit(draw_text("Passage", self.fonts["bold"], self.theme["muted"]), (right.left+16, py)); py+=28
            for ln in wrap_lines(item["passage"], self.fonts["body"], right.width-32):
                self.screen.blit(draw_text(ln, self.fonts["body"], self.theme["text"]), (right.left+16, py)); py+=26

        # question
        y = left.top+60
        self.screen.blit(draw_text("Question", self.fonts["bold"], self.theme["muted"]), (left.left+16, y-28))
        for ln in wrap_lines(item.get("q",""), self.fonts["body"], left.width-32):
            self.screen.blit(draw_text(ln, self.fonts["body"], self.theme["text"]), (left.left+16, y)); y+=28
        y+=10

        # choices
        self.choice_rects=[]
        sel = (self.answers[name][self.q_i] or "")
        chs = item.get("choices", [])
        if chs:
            for i, ch in enumerate(chs):
                r = pygame.Rect(left.left+12, y, left.width-24, 52)
                draw_chip(self.screen, r, self.theme)
                letter = ["A","B","C","D"][i] if i<4 else "?"
                if sel == letter:
                    pygame.draw.rect(self.screen, self.theme["accent"], r, 3, border_radius=12)
                badge = pygame.Rect(r.left+10, r.top+10, 32, 32)
                pygame.draw.rect(self.screen, self.theme["accent"] if sel==letter else (160,160,170), badge, border_radius=8)
                self.screen.blit(draw_text(letter, self.fonts["bold"], (255,255,255)), (badge.x+8, badge.y+4))
                self.screen.blit(draw_text(ch, self.fonts["body"], self.theme["text"]), (badge.right+10, badge.top+4))
                self.choice_rects.append((r, letter))
                y+=60
        else:
            self.screen.blit(draw_text("(Unscored item — no choices)", self.fonts["body"], self.theme["muted"]), (left.left+16, y)); y+=30

        # nav buttons
        self.btn_prev = Button((left.left+16, left.bottom-56, 120,40), "Prev", icon="chev_left")
        self.btn_next = Button((left.left+146, left.bottom-56, 120,40), "Next", icon="chev_right")
        self.btn_submit = Button((left.right-156, left.bottom-56, 140,40), "Submit", icon="check")
        self.btn_prev.enabled = (self.q_i>0)
        self.btn_next.enabled = (self.q_i<total-1)
        for b in [self.btn_prev, self.btn_next, self.btn_submit]:
            b.draw(self.screen, self.theme, self.fonts)

        self.btn_lobby = Button((right.left+16, right.bottom-56 - (44 if self.btn_skip else 0) - 12, 120,40), "Lobby", icon="home")
        self.btn_lobby.draw(self.screen, self.theme, self.fonts)

        for e in events:
            if self.btn_prev.handle_event(e) and self.q_i>0: self.q_i-=1
            elif self.btn_next.handle_event(e) and self.q_i<total-1: self.q_i+=1
            elif self.btn_submit.handle_event(e): self.finish_exam()
            elif self.btn_lobby.handle_event(e):
                if not is_exam: self.state = S_LOBBY
            elif self.btn_skip and self.btn_skip.handle_event(e) and skip_enabled:
                self.start_section(self.sec_i+1)
            elif e.type==pygame.KEYDOWN:
                if e.unicode.lower()=="a": self.answers[name][self.q_i]="A"
                elif e.unicode.lower()=="b": self.answers[name][self.q_i]="B"
                elif e.unicode.lower()=="c": self.answers[name][self.q_i]="C"
                elif e.unicode.lower()=="d": self.answers[name][self.q_i]="D"
                elif e.key==pygame.K_RIGHT and self.q_i<total-1: self.q_i+=1
                elif e.key==pygame.K_LEFT and self.q_i>0: self.q_i-=1
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER): self.finish_exam()
                elif e.key==pygame.K_ESCAPE and not is_exam: self.state = S_LOBBY
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                for r, letter in self.choice_rects:
                    if r.collidepoint(e.pos):
                        self.answers[name][self.q_i] = letter
                        break
            elif e.type==pygame.DROPFILE:
                try:
                    p=e.file; self.sections_all=parse_exam(p); self.exam_path=p; self.state=S_LOBBY; self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex: self.toast.trigger(f"Load error: {ex}")
        self.tick_timer()
        self.draw_toast()

    def finish_exam(self):
        res = {}; tot_c=tot_t=0
        for name,items,_ in self.sections_all:
            c=t=0; wrong=[]
            ans = self.answers.get(name, [None]*len(items))
            for i,it in enumerate(items):
                if not it.get("choices"): continue
                t+=1
                key=(it.get("ans","") or "").strip().upper()
                usr=(ans[i] or "").strip().upper()
                if usr==key: c+=1
                else: wrong.append((i+1, it.get("q",""), key, usr or "—"))
            res[name]={"correct":c,"total":t,"wrong":wrong}
            tot_c+=c; tot_t+=t
        self.results={"by_section":res,"overall":{"correct":tot_c,"total":tot_t}}
        self.state = S_RESULTS

    def save_report_txt(self):
        base=_user_data_dir(); path=os.path.join(base,"isee_results.txt")
        now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        L=[f"{APP_NAME} Results ({now})","="*64]
        gc=self.results["overall"]["correct"]; gt=self.results["overall"]["total"]
        overall=(100.0*gc/gt) if gt else 0.0
        for sec,r in self.results["by_section"].items():
            p=(100.0*r["correct"]/r["total"]) if r["total"] else 0.0
            L.append(f"{sec}: {r['correct']}/{r['total']} ({p:.1f}%)")
            if r["wrong"]:
                L.append("  Wrong:")
                for (num,q,right,yours) in r["wrong"][:50]:
                    L.append(f"    Q{num}: you={yours} | correct={right} | {q}")
        L+=["-"*64, f"OVERALL: {gc}/{gt} ({overall:.1f}%)"]
        with open(path,"w",encoding="utf-8") as f: f.write("\n".join(L))
        self.toast.trigger(f"Saved {os.path.basename(path)}")

    def export_results_json(self):
        base=_user_data_dir(); path=os.path.join(base,"isee_results.json")
        with open(path,"w",encoding="utf-8") as f: json.dump(self.results,f,ensure_ascii=False,indent=2)
        self.toast.trigger(f"Saved {os.path.basename(path)}")

    def scr_results(self, events):
        self.fill_bg(); self.header()
        card = pygame.Rect(int(self.W*0.08), 90, int(self.W*0.84), self.H-140)
        blit_shadowed_card(self.screen, card, self.theme)
        y=card.top+16
        self.screen.blit(draw_text("Results", self.fonts["h1"], self.theme["text"]), (card.left+20, y)); y+=48
        if not self.results:
            self.screen.blit(draw_text("No results yet.", self.fonts["body"], self.theme["muted"]), (card.left+20, y))
        else:
            gc=self.results["overall"]["correct"]; gt=self.results["overall"]["total"]
            overall=(100.0*gc/gt) if gt else 0.0
            self.screen.blit(draw_text(f"OVERALL: {gc}/{gt} ({overall:.1f}%)", self.fonts["bold"], self.theme["text"]), (card.left+20, y)); y+=40
            for sec,r in self.results["by_section"].items():
                p=(100.0*r["correct"]/r["total"]) if r["total"] else 0.0
                self.screen.blit(draw_text(f"{sec}: {r['correct']}/{r['total']} ({p:.1f}%)", self.fonts["body"], self.theme["muted"]), (card.left+20, y)); y+=28

        self.btn_save = Button(pygame.Rect(0,0,0,0), "Save TXT", icon="file_text")
        self.btn_export = Button(pygame.Rect(0,0,0,0), "Export JSON", icon="code")
        self.btn_lobby = Button(pygame.Rect(0,0,0,0), "Section Lobby", icon="section")
        self.btn_home = Button(pygame.Rect(0,0,0,0), "Home", icon="home")
        layout_button_row(card, [self.btn_save, self.btn_export, self.btn_lobby, self.btn_home],
                          self.theme, self.fonts, align="left", pad_x=20, pad_y=20, gap=12, min_w=150, max_w=220, h=44)

        for e in events:
            if self.btn_save.handle_event(e): self.save_report_txt()
            elif self.btn_export.handle_event(e): self.export_results_json()
            elif self.btn_lobby.handle_event(e): self.state = S_LOBBY
            elif self.btn_home.handle_event(e): self.state = S_HOME
            elif e.type==pygame.DROPFILE:
                try:
                    p=e.file; self.sections_all=parse_exam(p); self.exam_path=p; self.state=S_LOBBY; self.toast.trigger(f"Loaded: {os.path.basename(p)}")
                except Exception as ex: self.toast.trigger(f"Load error: {ex}")
        self.draw_toast()

    # ---------- Builder (Exam Builder UI) ----------
    def scr_builder(self, events):
        self.fill_bg(); self.header()
        # layout
        left = pygame.Rect(20, 90, int(self.W*0.32), self.H-140)
        mid  = pygame.Rect(left.right+12, 90, int(self.W*0.32), self.H-140)
        right= pygame.Rect(mid.right+12, 90, self.W - (mid.right+32), self.H-140)
        for r in (left, mid, right): blit_shadowed_card(self.screen, r, self.theme)

        # left: sections list
        self.screen.blit(draw_text("Sections", self.fonts["bold"], self.theme["text"]), (left.x+14, left.y+12))
        by = left.y+44
        self.btn_add_sec = Button((left.x+14, left.bottom-52, 130,40), "Add Section")
        self.btn_del_sec = Button((left.x+154, left.bottom-52, 130,40), "Delete Section")
        self.btn_add_sec.draw(self.screen, self.theme, self.fonts)
        self.btn_del_sec.draw(self.screen, self.theme, self.fonts)

        self._section_btns = []
        for i, sec in enumerate(self.builder_sections):
            label = f"{i+1}. {sec.get('name','Untitled')}"
            btn = Button((left.x+14, by, left.width-28, 40), label)
            if i == self.b_sel_sec:
                pygame.draw.rect(self.screen, self.theme["accent"], btn.rect, 3, border_radius=12)
            btn.draw(self.screen, self.theme, self.fonts); self._section_btns.append((i, btn)); by += 46

        # mid: items list for selected section
        self.screen.blit(draw_text("Items", self.fonts["bold"], self.theme["text"]), (mid.x+14, mid.y+12))
        by = mid.y+44
        self.btn_add_item = Button((mid.x+14, mid.bottom-52, 130,40), "Add Item")
        self.btn_del_item = Button((mid.x+154, mid.bottom-52, 130,40), "Delete Item")
        self.btn_add_item.draw(self.screen, self.theme, self.fonts)
        self.btn_del_item.draw(self.screen, self.theme, self.fonts)
        self._item_btns = []
        if 0 <= self.b_sel_sec < len(self.builder_sections):
            items = self.builder_sections[self.b_sel_sec].get("items", [])
            for j, it in enumerate(items):
                label = f"Q{j+1}"
                btn = Button((mid.x+14, by, mid.width-28, 40), label)
                if j == self.b_sel_item:
                    pygame.draw.rect(self.screen, self.theme["accent"], btn.rect, 3, border_radius=12)
                btn.draw(self.screen, self.theme, self.fonts); self._item_btns.append((j, btn)); by += 46

        # right: editors
        x = right.x+14; y = right.y+12
        self.screen.blit(draw_text("Editor", self.fonts["bold"], self.theme["text"]), (x, y)); y+=40
        # Section name + time
        self.in_sec_name.rect = pygame.Rect(x, y, right.width-170, 36)
        self.in_time.rect = pygame.Rect(self.in_sec_name.rect.right+10, y, 140, 36); y+=48
        # Question
        self.screen.blit(draw_text("Question", self.fonts["bold"], self.theme["muted"]), (x, y)); y+=8
        self.in_q.rect = pygame.Rect(x, y+20, right.width-20, 96); y+=120
        # Passage
        self.screen.blit(draw_text("Passage (optional)", self.fonts["bold"], self.theme["muted"]), (x, y)); y+=8
        self.in_passage.rect = pygame.Rect(x, y+20, right.width-20, 96); y+=120
        # Choices
        self.screen.blit(draw_text("Choices A–D", self.fonts["bold"], self.theme["muted"]), (x, y)); y+=8
        w2 = (right.width-28)//2
        for row in range(2):
            for col in range(2):
                idx = row*2+col
                self.in_choice[idx].rect = pygame.Rect(x + col*(w2+8), y+20+row*48, w2, 36)
        y += 120
        # Answer
        self.in_ans.rect = pygame.Rect(x, y, 100, 36)
        self.btn_back_home = Button(pygame.Rect(0,0,0,0), "Back")
        self.btn_save_as = Button(pygame.Rect(0,0,0,0), "Save As...")
        # lay them out aligned to the right edge of the right panel
        layout_button_row(right, [self.btn_back_home, self.btn_save_as],
                          self.theme, self.fonts, align="right", pad_x=14, pad_y=12, gap=10, min_w=130, max_w=180, h=40)

        # draw inputs
        for inp in [self.in_sec_name, self.in_time, self.in_q, self.in_passage, *self.in_choice, self.in_ans]:
            inp.draw(self.screen, self.fonts, self.theme)

        # events
        for e in events:
            # inputs
            for inp in [self.in_sec_name, self.in_time, self.in_q, self.in_passage, *self.in_choice, self.in_ans]:
                inp.handle_event(e)

            if self.btn_back_home.handle_event(e):
                self.state = S_HOME

            if self.btn_add_sec.handle_event(e):
                self.builder_sections.append({"name":"Untitled","time_minutes":None,"items":[]})
                self.b_sel_sec = len(self.builder_sections)-1; self.b_sel_item = -1
                self._sync_inputs_from_model()

            if self.btn_del_sec.handle_event(e) and 0 <= self.b_sel_sec < len(self.builder_sections):
                del self.builder_sections[self.b_sel_sec]
                self.b_sel_sec = -1; self.b_sel_item = -1
                self._sync_inputs_from_model()

            for idx, btn in self._section_btns:
                if btn.handle_event(e):
                    self._apply_inputs_to_model()
                    self.b_sel_sec = idx; self.b_sel_item = -1
                    self._sync_inputs_from_model()

            if self.btn_add_item.handle_event(e) and 0 <= self.b_sel_sec < len(self.builder_sections):
                sec = self.builder_sections[self.b_sel_sec]
                sec.setdefault("items", []).append({"q":"","choices":[],"ans":"","passage":""})
                self.b_sel_item = len(sec["items"])-1
                self._sync_inputs_from_model()

            if self.btn_del_item.handle_event(e) and 0 <= self.b_sel_sec < len(self.builder_sections):
                sec = self.builder_sections[self.b_sel_sec]
                if 0 <= self.b_sel_item < len(sec.get("items",[])):
                    del sec["items"][self.b_sel_item]
                    self.b_sel_item = -1
                    self._sync_inputs_from_model()

            for jdx, btn in self._item_btns:
                if btn.handle_event(e):
                    self._apply_inputs_to_model()
                    self.b_sel_item = jdx
                    self._sync_inputs_from_model()

            if self.btn_save_as.handle_event(e):
                self._apply_inputs_to_model()
                data = {"sections": self.builder_sections}
                # defaults
                for sec in data["sections"]:
                    sec.setdefault("name","Untitled")
                    if sec.get("time_minutes","") == "": sec["time_minutes"]=None
                    for it in sec.get("items",[]):
                        it.setdefault("q",""); it.setdefault("choices",[])
                        it.setdefault("ans",""); it.setdefault("passage","")
                # choose path (lazy Tk root to prevent .app launch issues)
                saved = False
                try:
                    if _ensure_tk_root() and _TK_ROOT:
                        path = _fd.asksaveasfilename(parent=_TK_ROOT,
                                                     defaultextension=".json",
                                                     filetypes=[("JSON files","*.json")],
                                                     title="Save Exam JSON As...")
                    else:
                        path = ""
                    if path:
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        self.toast.trigger(f"Saved: {os.path.basename(path)}")
                        saved = True
                except Exception as ex:
                    saved = False
                if not saved:
                    fallback = os.path.join(_user_data_dir(), "testify_exam.json")
                    try:
                        with open(fallback,"w",encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        self.toast.trigger(f"Saved (fallback): {os.path.basename(fallback)}")
                    except Exception as ex:
                        self.toast.trigger(f"Save failed: {ex}")

        self.draw_toast()

    # ---------------------------- loop (main event loop) ----------------------------
    def run(self):
        running=True
        while running:
            events=[]
            for e in pygame.event.get():
                if e.type==pygame.QUIT: running=False
                elif e.type==pygame.VIDEORESIZE: self.on_resize(e.w,e.h)
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    # dismiss toast on click
                    if self.toast.rect and self.toast.rect.collidepoint(e.pos):
                        self.toast.phase="idle"; self.toast.msg=""; self.toast.rect=None
                else: events.append(e)
            if self.state==S_HOME: self.scr_home(events)
            elif self.state==S_SETTINGS: self.scr_settings(events)
            elif self.state==S_HELP: self.scr_help(events)
            elif self.state==S_LOBBY: self.scr_lobby(events)
            elif self.state==S_SECTION: self.scr_section(events)
            elif self.state==S_RESULTS: self.scr_results(events)
            elif self.state==S_BUILDER: self.scr_builder(events)
            pygame.display.flip(); self.clock.tick(60)

def main():
    try:
        _log_runtime("Boot")
        initial = sys.argv[1] if len(sys.argv)>1 and os.path.isfile(sys.argv[1]) else None
        App(initial).run()
        _log_runtime("Normal exit")
    except Exception as ex:
        # Write full traceback to the same log file (so you can debug later, hopefully)
        try:
            import traceback
            lp = os.path.join(_user_data_dir(), "testify_crash.log")
            with open(lp, "a", encoding="utf-8") as f:
                f.write("\n===== FATAL @ %s =====\n" % datetime.datetime.now().isoformat(timespec="seconds"))
                traceback.print_exc(file=f)
        except Exception:
            pass
        # On macOS, show a visible alert so the user isn't left guessing why it just died
        if sys.platform == "darwin":
            try:
                safe_msg = str(ex).replace('"', '\\"')
                os.system(f'''osascript -e 'display alert "Testify crashed" message "{safe_msg}"' ''')
            except Exception:
                pass

if __name__ == "__main__":
    main()
