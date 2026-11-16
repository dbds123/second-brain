#!/usr/bin/env python3
"""
danbds Admin-Panel
==================

Ein kleiner Webserver, der zeigt, was auf dem Render-Server los ist:
Renders (mit Fortschritt und Restzeit), Warteschlange, GPU-Temperatur mit
Verlauf, CPU/RAM/Speicher, laufende Claude-Sitzungen, fertige Videos und
geplante Uploads. Renders lassen sich pausieren und fortsetzen.

Nur Python-3-Standardbibliothek. Liest fast nur. Die einzigen Eingriffe:
  * Pause/Weiter eines Renders (Signal STOP/CONT an den Blender-Prozess)
  * optional der Hitzewächter (gleiches Prinzip, standardmäßig AUS)
  * Vorschaubilder für Videos (ffmpeg, niedrigste Priorität, eigener Cache)

Start:   python3 server.py                (echte Daten)
         python3 server.py --demo         (Beispieldaten, zum Testen)
Optionen: --port 8090 --host 0.0.0.0 --config config.json
"""

import argparse
import fnmatch
import hashlib
import http.server
import json
import math
import os
import random
import re
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
VERSION = "1.0"

# --------------------------------------------------------------------------
# Einstellungen
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "port": 8090,
    "host": "0.0.0.0",
    "data_dir": "data",
    "sample_seconds": 5,          # wie oft Werte gemessen werden
    "history_seconds": 15,        # Abstand der Verlaufspunkte
    "history_hours": 48,
    "video_scan_seconds": 60,
    "max_videos": 150,
    "gpu_lock": "~/kanal-2-blender/gpu.lock",
    "status_page": "http://{host}:8088/alle/",
    # Wer darf Knöpfe drücken: nur Heimnetz, Tailscale und der Server selbst
    "allowed_networks": ["127.0.0.0/8", "192.168.0.0/16", "10.0.0.0/8",
                         "172.16.0.0/12", "100.64.0.0/10", "::1/128",
                         "fd7a:115c:a1e0::/48"],
    "heat_guard": {
        "enabled": False,         # erst einschalten, wenn Daniel es will
        "pause_at": 80,
        "resume_at": 68,
    },
    "warn": {"gpu_temp": 75, "gpu_temp_bad": 82, "disk_percent": 90,
             "ram_percent": 90},
    "projects": [
        {"id": "coin-island", "name": "Coin Island", "color": "#e0a526",
         "match": ["coin-island", "coin_island", "coinisland"]},
        {"id": "step-three", "name": "Step Three", "color": "#9b6bff",
         "match": ["step-three", "step_three", "stepthree"]},
        {"id": "shift-over", "name": "Shift Over", "color": "#22b8a6",
         "match": ["shift-over", "shift_over", "shiftover"]},
        # Sammelbecken, wenn nur der Ordner bekannt ist
        {"id": "kanal-2", "name": "Kanal 2", "color": "#5b8def",
         "match": ["kanal-2", "kanal_2"]},
    ],
    "videos": [
        {"dir": "~/statusseite/alle/media", "recursive": True},
        {"dir": "~/kanal-2-blender", "recursive": True},
        {"dir": "~/coin-island-blender", "recursive": True},
    ],
    # Ordnernamen, die beim Video-Suchen übersprungen werden (Einzelbilder)
    "video_skip_dirs": ["frames", "frame", "tmp", "cache", "__pycache__",
                        ".git", "node_modules", "textures"],
}


def deep_merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path and Path(path).exists():
        with open(path, encoding="utf-8") as f:
            cfg = deep_merge(cfg, json.load(f))
    return cfg


def expand(p):
    return Path(os.path.expanduser(str(p)))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# --------------------------------------------------------------------------
# Kleine Hilfen für /proc
# --------------------------------------------------------------------------

CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
try:
    BOOT_TIME = next(int(l.split()[1]) for l in open("/proc/stat")
                     if l.startswith("btime"))
except Exception:
    BOOT_TIME = int(time.time())


def read_text(path, limit=None):
    try:
        with open(path, "rb") as f:
            data = f.read(limit) if limit else f.read()
        return data.decode("utf-8", "replace")
    except Exception:
        return None


def proc_cmdline(pid):
    raw = read_text(f"/proc/{pid}/cmdline")
    if not raw:
        return []
    return [a for a in raw.split("\0") if a != ""]


def proc_stat(pid):
    """state, ppid, utime+stime (ticks), starttime (epoch), pgrp"""
    raw = read_text(f"/proc/{pid}/stat")
    if not raw:
        return None
    try:
        rest = raw[raw.rindex(")") + 2:].split()
        state = rest[0]
        ppid = int(rest[1])
        pgrp = int(rest[2])
        ticks = int(rest[11]) + int(rest[12])
        start = BOOT_TIME + int(rest[19]) / CLK_TCK
        rss = int(rest[21]) * os.sysconf("SC_PAGE_SIZE")
        return {"state": state, "ppid": ppid, "pgrp": pgrp, "ticks": ticks,
                "start": start, "rss": rss}
    except Exception:
        return None


def proc_environ(pid):
    raw = read_text(f"/proc/{pid}/environ")
    env = {}
    if raw:
        for item in raw.split("\0"):
            if "=" in item:
                k, v = item.split("=", 1)
                if k.startswith("PANEL_"):
                    env[k] = v
    return env


def proc_cwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except Exception:
        return None


def proc_stdout_file(pid):
    """Wenn die Ausgabe in eine Datei umgeleitet ist: deren Pfad."""
    for fd in ("1", "2"):
        try:
            target = os.readlink(f"/proc/{pid}/fd/{fd}")
        except Exception:
            continue
        if target.startswith("/") and os.path.isfile(target):
            return target
    return None


def tail(path, size=48_000):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            f.seek(max(0, end - size))
            return f.read().decode("utf-8", "replace")
    except Exception:
        return ""


def all_pids():
    for name in os.listdir("/proc"):
        if name.isdigit():
            yield int(name)


def run(cmd, timeout=4):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def ip_in(ip, cidr):
    import ipaddress
    try:
        return ipaddress.ip_address(ip.split("%")[0]) in \
            ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return False


# --------------------------------------------------------------------------
# Projekte zuordnen
# --------------------------------------------------------------------------

class Projects:
    def __init__(self, cfg):
        self.items = cfg["projects"]

    def find(self, *texts):
        """Erster Text mit Treffer gewinnt (z. B. .blend vor Ordner)."""
        for t in texts:
            if not t:
                continue
            hay = t.lower()
            for p in self.items:
                if p["id"] in hay or any(m.lower() in hay
                                         for m in p.get("match", [])):
                    return p["id"]
        return "andere"

    def public(self):
        return [{"id": p["id"], "name": p["name"], "color": p["color"]}
                for p in self.items] + \
            [{"id": "andere", "name": "Andere", "color": "#8a8f98"}]


# --------------------------------------------------------------------------
# Messen: GPU, CPU, RAM, Speicher
# --------------------------------------------------------------------------

def read_gpu():
    q = ("name,temperature.gpu,utilization.gpu,memory.used,memory.total,"
         "power.draw,power.limit,fan.speed,clocks.gr")
    out = run(["nvidia-smi", f"--query-gpu={q}",
               "--format=csv,noheader,nounits"])
    if not out:
        return None
    parts = [p.strip() for p in out.strip().splitlines()[0].split(",")]

    def num(x):
        try:
            return float(x)
        except Exception:
            return None
    gpu = {"name": parts[0], "temp": num(parts[1]), "util": num(parts[2]),
           "mem_used": num(parts[3]), "mem_total": num(parts[4]),
           "power": num(parts[5]), "power_limit": num(parts[6]),
           "fan": num(parts[7]), "clock": num(parts[8])}
    apps = run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits"]) or ""
    gpu["procs"] = {}
    for line in apps.strip().splitlines():
        try:
            pid, mem = [x.strip() for x in line.split(",")]
            gpu["procs"][int(pid)] = float(mem)
        except Exception:
            pass
    return gpu


class CpuMeter:
    def __init__(self):
        self.last = None

    def percent(self):
        try:
            vals = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        except Exception:
            return None
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals[:8])
        res = None
        if self.last:
            dt = total - self.last[0]
            di = idle - self.last[1]
            if dt > 0:
                res = round(100 * (1 - di / dt), 1)
        self.last = (total, idle)
        return res


def read_cpu_temp():
    base = Path("/sys/class/hwmon")
    best = None
    try:
        for hw in base.iterdir():
            name = read_text(hw / "name") or ""
            if name.strip() not in ("coretemp", "k10temp", "zenpower"):
                continue
            for f in sorted(hw.glob("temp*_input")):
                label = read_text(str(f).replace("_input", "_label")) or ""
                v = int(read_text(f) or 0) / 1000
                if "Package" in label or "Tctl" in label:
                    return v
                best = max(best or 0, v)
    except Exception:
        pass
    return best


def read_mem():
    info = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    except Exception:
        return None
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return {"total": total, "used": total - avail,
            "swap_total": info.get("SwapTotal", 0),
            "swap_used": info.get("SwapTotal", 0) - info.get("SwapFree", 0)}


def read_disks():
    seen, out = set(), []
    for mount in ["/", str(HOME)] + [l.split()[1] for l in
                                     (read_text("/proc/mounts") or "").splitlines()
                                     if l.startswith("/dev/")]:
        try:
            st = os.statvfs(mount)
        except Exception:
            continue
        key = (st.f_blocks, st.f_fsid if hasattr(st, "f_fsid") else mount)
        if key in seen or st.f_blocks == 0:
            continue
        seen.add(key)
        total = st.f_blocks * st.f_frsize
        if total < 2 * 1024**3:      # kleine Boot-Partitionen weglassen
            continue
        free = st.f_bavail * st.f_frsize
        out.append({"mount": mount, "total": total, "used": total - free})
    return out


# --------------------------------------------------------------------------
# Renders, Warteschlange, Claude-Sitzungen erkennen
# --------------------------------------------------------------------------

IMG_EXT = (".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".webp", ".bmp")
RE_FRA = re.compile(r"Fra:(\d+)")
RE_SAVED = re.compile(r"Saved: '([^']+)'")
RE_TIME = re.compile(r"Time: (\d+):(\d+)\.(\d+)")
# Eigene Render-Skripte (z. B. folge2_ci.py): "RENDER 303 2.5s/Bild"
RE_RENDER = re.compile(r"RENDER\s+(\d+)(?:\s+([\d.,]+)\s*s\s*/\s*Bild)?",
                       re.I)
RE_NUM_END = re.compile(r"(\d+)\.[A-Za-z]+$")


def parse_blender_args(argv):
    """Holt .blend-Datei, Bildbereich und Ausgabepfad aus der Befehlszeile."""
    r = {"blend": None, "start": None, "end": None, "frames": [],
         "out": None, "anim": False, "scripts": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a.endswith(".blend") and r["blend"] is None:
            r["blend"] = a
        elif a in ("-s", "--frame-start") and nxt:
            r["start"] = _int(nxt); i += 1
        elif a in ("-e", "--frame-end") and nxt:
            r["end"] = _int(nxt); i += 1
        elif a in ("-f", "--render-frame") and nxt:
            for part in nxt.split(","):
                if ".." in part:
                    s, e = part.split("..")
                    if _int(s) is not None and _int(e) is not None:
                        r["frames"].extend(range(_int(s), _int(e) + 1))
                elif _int(part) is not None:
                    r["frames"].append(_int(part))
            i += 1
        elif a in ("-o", "--render-output") and nxt:
            r["out"] = nxt; i += 1
        elif a in ("-a", "--render-anim"):
            r["anim"] = True
        elif a in ("-P", "--python") and nxt:
            r["scripts"].append(nxt); i += 1
        elif a == "--":
            _parse_script_args(argv[i + 1:], r)
            break
        i += 1
    return r


def _parse_script_args(rest, r):
    """Argumente nach "--" für eigene Render-Skripte, z. B.
    "render ../video/frames 0 1154 1": Ordner, Start, Ende, Schritt."""
    nums = [_int(a) for a in rest if _int(a) is not None]
    for j, a in enumerate(rest):
        if a.lower() == "render" and j + 1 < len(rest) and \
                _int(rest[j + 1]) is None and r["out"] is None:
            r["out"] = rest[j + 1]
    if r["start"] is None and r["end"] is None and len(nums) >= 2 \
            and nums[1] >= nums[0]:
        r["start"], r["end"] = nums[0], nums[1]
        if len(nums) >= 3 and nums[2] > 1:
            r["step"] = nums[2]


def _int(x):
    try:
        return int(x)
    except Exception:
        return None


def count_output_frames(out_pattern, blend, since, cwd=None):
    """Zählt Bilder im Ausgabeordner, die seit Render-Start entstanden."""
    if not out_pattern:
        return None, None
    p = out_pattern
    if p.startswith("//") and blend:
        p = str(Path(blend).resolve().parent / p[2:])
    p = os.path.expanduser(p)
    if not os.path.isabs(p) and cwd:
        p = os.path.join(cwd, p)
    if os.path.isdir(p):
        folder, prefix = p, ""
    else:
        folder, base = os.path.split(p)
        prefix = base.split("#")[0]
    try:
        n, newest = 0, None
        with os.scandir(folder or ".") as it:
            for e in it:
                if not e.name.startswith(prefix) or \
                        not e.name.lower().endswith(IMG_EXT):
                    continue
                st = e.stat()
                if st.st_mtime >= since - 2:
                    n += 1
                    if newest is None or st.st_mtime > newest[1]:
                        newest = (e.path, st.st_mtime)
        return n, newest[0] if newest else None
    except Exception:
        return None, None


class ProcessScanner:
    """Findet Blender-Renders, wartende flock-Aufträge und Claude-Sitzungen."""

    def __init__(self, cfg, projects):
        self.cfg = cfg
        self.projects = projects
        self.lock_name = os.path.basename(os.path.expanduser(cfg["gpu_lock"]))
        self.progress = {}        # pid -> [(t, done)]
        self.cpu_last = {}        # pid -> (t, ticks)

    def cpu_percent(self, pid, ticks, now):
        last = self.cpu_last.get(pid)
        self.cpu_last[pid] = (now, ticks)
        if not last or now <= last[0]:
            return None
        return round(100 * (ticks - last[1]) / CLK_TCK / (now - last[0]), 1)

    def scan(self, gpu):
        now = time.time()
        procs = {}
        children = {}
        for pid in all_pids():
            st = proc_stat(pid)
            if not st:
                continue
            argv = proc_cmdline(pid)
            if not argv:
                continue
            procs[pid] = (st, argv)
            children.setdefault(st["ppid"], []).append(pid)

        def descendants(pid):
            out, todo = [], list(children.get(pid, []))
            while todo:
                c = todo.pop()
                out.append(c)
                todo.extend(children.get(c, []))
            return out

        def is_blender(argv):
            exe = os.path.basename(argv[0]).lower()
            if exe.startswith(("python", "sh", "bash")) and len(argv) > 1:
                exe = os.path.basename(argv[1]).lower()   # Startskript
            return exe.startswith("blender") and ("-b" in argv or
                                                  "--background" in argv)

        renders, queue, post, sessions, daemons = [], [], [], [], []
        gpu_procs = (gpu or {}).get("procs", {})

        for pid, (st, argv) in procs.items():
            exe = os.path.basename(argv[0]).lower()
            joined = " ".join(argv)

            # --- Blender-Render
            if is_blender(argv):
                # Ein Blender, dessen Eltern auch Blender ist, nicht doppelt
                parent = procs.get(st["ppid"])
                if parent and is_blender(parent[1]):
                    continue
                renders.append(self._render_info(pid, st, argv, now,
                                                 gpu_procs))
                continue

            # --- wartet auf die GPU (flock ohne laufendes Blender darunter)
            if exe == "flock" and self.lock_name in joined:
                kids = descendants(pid)
                if not any(is_blender(procs[k][1]) for k in kids
                           if k in procs):
                    env = proc_environ(pid)
                    pa = parse_blender_args(argv)
                    blend = pa["blend"]
                    title = env.get("PANEL_TITEL") or env.get("PANEL_TITLE") \
                        or (Path(pa["scripts"][0]).stem if pa["scripts"]
                            else Path(blend).stem if blend else
                            " ".join(argv[2:])[:80])
                    queue.append({
                        "pid": pid, "title": title, "blend": blend,
                        "project": env.get("PANEL_PROJEKT") or
                        self.projects.find(blend, joined, proc_cwd(pid)),
                        "since": st["start"],
                        "frames": _int(env.get("PANEL_BILDER")),
                    })
                continue

            # --- Nachbearbeitung (ffmpeg / post.py) für die Projekte
            if exe in ("ffmpeg",) or (exe.startswith("python") and
                                      any(a.endswith("post.py")
                                          for a in argv)):
                cwd = proc_cwd(pid) or ""
                proj = self.projects.find(joined, cwd)
                if proj != "andere":
                    post.append({"pid": pid, "project": proj,
                                 "title": self._short_cmd(argv),
                                 "since": st["start"],
                                 "cpu": self.cpu_percent(pid, st["ticks"],
                                                         now)})
                continue

            # --- Claude
            if "claude" in joined.lower():
                # Programm heißt "claude" oder liegt unter
                # ~/.local/share/claude/versions/<nummer>
                is_claude = exe == "claude" or \
                    any("/claude/versions/" in a for a in argv[:2]) or any(
                        os.path.basename(a).lower() in ("claude", "cli.js",
                                                        "claude.js")
                        and "claude" in a.lower() for a in argv[:3])
                if not is_claude:
                    continue
                if "--session-id" in argv or any(a.startswith("--session-id=")
                                                 for a in argv):
                    sid = None
                    for i, a in enumerate(argv):
                        if a == "--session-id" and i + 1 < len(argv):
                            sid = argv[i + 1]
                        elif a.startswith("--session-id="):
                            sid = a.split("=", 1)[1]
                    cwd = proc_cwd(pid) or ""
                    env = proc_environ(pid)
                    sessions.append({
                        "pid": pid, "id": sid, "cwd": cwd.replace(str(HOME),
                                                                   "~"),
                        "project": env.get("PANEL_PROJEKT") or
                        self.projects.find(
                            " ".join(" ".join(procs[k][1])
                                     for k in descendants(pid)
                                     if k in procs), joined, cwd),
                        "started": st["start"], "rss": st["rss"],
                        "cpu": self.cpu_percent(pid, st["ticks"], now),
                        "busy": any(procs.get(k, ({}, [""]))[0].get("state")
                                    == "R" for k in descendants(pid)),
                        "children": len(descendants(pid)),
                    })
                elif "remote-control" in joined or "--capacity" in joined \
                        or " rc" in joined:
                    cap = None
                    for i, a in enumerate(argv):
                        if a == "--capacity" and i + 1 < len(argv):
                            cap = _int(argv[i + 1])
                        elif a.startswith("--capacity="):
                            cap = _int(a.split("=", 1)[1])
                    daemons.append({"pid": pid, "capacity": cap or 1,
                                    "started": st["start"],
                                    "rss": st["rss"]})

        # Doppelte Sitzungen (Unterprozesse mit gleicher ID) zusammenfassen
        uniq = {}
        for s in sorted(sessions, key=lambda s: s["started"]):
            key = s["id"] or s["pid"]
            if key not in uniq:
                uniq[key] = s
        sessions = list(uniq.values())

        # Alte Fortschrittsdaten aufräumen
        alive = {r["pid"] for r in renders}
        for pid in list(self.progress):
            if pid not in alive:
                del self.progress[pid]
        for pid in list(self.cpu_last):
            if pid not in procs:
                del self.cpu_last[pid]

        queue.sort(key=lambda q: q["since"])
        cap = sum(d["capacity"] for d in daemons) if daemons else None
        return {"renders": renders, "queue": queue, "post": post,
                "sessions": sessions, "daemons": daemons,
                "slots": {"used": len(sessions), "capacity": cap}}

    def _short_cmd(self, argv):
        name = os.path.basename(argv[0])
        rest = [os.path.basename(a) for a in argv[1:]
                if a.endswith((".mp4", ".py", ".mov", ".wav"))]
        return (name + " " + " ".join(rest[-2:])).strip()

    def _render_info(self, pid, st, argv, now, gpu_procs):
        pa = parse_blender_args(argv)
        env = proc_environ(pid)
        blend = pa["blend"]
        cwd = proc_cwd(pid)
        if blend and not os.path.isabs(blend) and cwd:
            blend = os.path.join(cwd, blend)

        start = pa["start"]
        end = pa["end"]
        if pa["frames"]:
            start, end = min(pa["frames"]), max(pa["frames"])
        if env.get("PANEL_START"):
            start = _int(env["PANEL_START"])
        if env.get("PANEL_ENDE"):
            end = _int(env["PANEL_ENDE"])
        total = _int(env.get("PANEL_BILDER"))
        if total is None and start is not None and end is not None:
            total = (end - start) // pa.get("step", 1) + 1
        if total is None and pa["frames"]:
            total = len(pa["frames"])

        # 1) Log-Datei auswerten (wenn die Ausgabe in eine Datei geht)
        logfile = env.get("PANEL_LOG") or proc_stdout_file(pid)
        frame, last_saved, frame_times, log_tail = None, None, [], []
        if logfile:
            text = tail(logfile)
            for m in RE_FRA.finditer(text):
                frame = int(m.group(1))
            for m in RE_RENDER.finditer(text):
                frame = int(m.group(1))
                if m.group(2):
                    try:
                        frame_times.append(float(m.group(2).replace(",",
                                                                    ".")))
                    except ValueError:
                        pass
            saved = RE_SAVED.findall(text)
            if saved:
                last_saved = saved[-1]
                m = RE_NUM_END.search(last_saved)
                if m and frame is None:
                    frame = int(m.group(1))
            for m in RE_TIME.finditer(text):
                frame_times.append(int(m.group(1)) * 60 + int(m.group(2)) +
                                   int(m.group(3)) / 100)
            log_tail = [l for l in text.splitlines() if l.strip()][-4:]

        # 2) Ausgabeordner zählen
        done, newest = count_output_frames(pa["out"], blend, st["start"],
                                           cwd)
        if newest and not last_saved:
            last_saved = newest

        # Bildnummer aus dem Log ist genauer als Dateien zählen (ein
        # fortgesetzter Render überspringt fertige Bilder)
        if frame is not None and start is not None:
            done = max(0, (frame - start) // pa.get("step", 1))
        if done is None and frame is not None and total:
            done = None   # ohne Startbild nicht sicher
        if frame is None and done is not None and start is not None:
            frame = start + done

        # Restzeit aus den letzten 10 Minuten
        eta, spf = None, None
        hist = self.progress.setdefault(pid, [])
        if done is not None:
            if not hist or hist[-1][1] != done:
                hist.append((now, done))
            cutoff = now - 600
            while len(hist) > 2 and hist[0][0] < cutoff:
                hist.pop(0)
            if len(hist) >= 2 and hist[-1][1] > hist[0][1]:
                spf = (hist[-1][0] - hist[0][0]) / (hist[-1][1] - hist[0][1])
        if spf is None and frame_times:
            spf = sum(frame_times[-10:]) / len(frame_times[-10:])
        if spf is None and done:
            spf = (now - st["start"]) / done
        if spf and total and done is not None:
            eta = now + max(0, total - done) * spf

        return {
            "pid": pid,
            "title": env.get("PANEL_TITEL") or env.get("PANEL_TITLE") or
            (Path(pa["scripts"][0]).stem if pa["scripts"] else
             Path(blend).stem if blend else "Blender"),
            "project": env.get("PANEL_PROJEKT") or
            self.projects.find(blend, " ".join(argv), cwd),
            "blend": (blend or "").replace(str(HOME), "~"),
            "state": "pausiert" if st["state"] == "T" else "läuft",
            "started": st["start"],
            "frame": frame, "start": start, "end": end,
            "done": done, "total": total,
            "sec_per_frame": round(spf, 2) if spf else None,
            "eta": eta,
            "cpu": self.cpu_percent(pid, st["ticks"], now),
            "rss": st["rss"],
            "gpu_mem": gpu_procs.get(pid),
            "last_frame": last_saved,
            "log_tail": log_tail,
        }


def signal_tree(pid, sig):
    """Signal an Prozess und alle Unterprozesse."""
    kids = {}
    for p in all_pids():
        st = proc_stat(p)
        if st:
            kids.setdefault(st["ppid"], []).append(p)
    todo, hit = [pid], []
    while todo:
        p = todo.pop()
        try:
            os.kill(p, sig)
            hit.append(p)
        except ProcessLookupError:
            pass
        todo.extend(kids.get(p, []))
    return hit


# --------------------------------------------------------------------------
# Videos und Vorschaubilder
# --------------------------------------------------------------------------

VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v", ".mkv")


class VideoLibrary:
    def __init__(self, cfg, projects, data_dir):
        self.cfg = cfg
        self.projects = projects
        self.thumb_dir = data_dir / "thumbs"
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = data_dir / "video_meta.json"
        self.meta = {}
        try:
            self.meta = json.loads(self.meta_file.read_text())
        except Exception:
            pass
        self.items = []
        self.by_id = {}
        self.lock = threading.Lock()
        self.thumb_queue = []
        self.has_ffmpeg = shutil.which("ffmpeg") is not None
        self.has_ffprobe = shutil.which("ffprobe") is not None

    def _vid(self, real):
        return hashlib.sha1(real.encode()).hexdigest()[:16]

    def scan(self):
        found = {}
        skip = set(self.cfg["video_skip_dirs"])
        for src in self.cfg["videos"]:
            root = expand(src["dir"])
            if not root.exists():
                continue
            pattern = src.get("pattern", "*")
            walker = os.walk(root, followlinks=False) if src.get(
                "recursive", True) else [(str(root), [], os.listdir(root))]
            for folder, dirs, files in walker:
                dirs[:] = [d for d in dirs if d.lower() not in skip and
                           not d.startswith(".")]
                for name in files:
                    if not name.lower().endswith(VIDEO_EXT):
                        continue
                    if not fnmatch.fnmatch(name, pattern):
                        continue
                    path = os.path.join(folder, name)
                    try:
                        real = os.path.realpath(path)
                        st = os.stat(real)
                    except Exception:
                        continue
                    if st.st_size < 10_000:
                        continue
                    vid = self._vid(real)
                    if vid in found:
                        continue
                    low = name.lower()
                    kind = "final" if "final" in low else \
                        "vorschau" if ("preview" in low or "vorschau" in low)\
                        else "entwurf"
                    found[vid] = {
                        "id": vid, "name": name, "path": real,
                        "show_path": real.replace(str(HOME), "~"),
                        "size": st.st_size, "mtime": st.st_mtime,
                        "project": self.projects.find(real),
                        "kind": kind,
                    }
        items = sorted(found.values(), key=lambda v: v["mtime"],
                       reverse=True)[: self.cfg["max_videos"]]
        for v in items:
            key = f'{v["id"]}-{int(v["mtime"])}-{v["size"]}'
            m = self.meta.get(key)
            v["meta_key"] = key
            if m:
                v.update({k: m.get(k) for k in ("duration", "width",
                                                 "height")})
            v["thumb"] = (self.thumb_dir / f"{key}.jpg").exists()
            if not m or not v["thumb"]:
                self.thumb_queue.append(v)
        with self.lock:
            self.items = items
            self.by_id = {v["id"]: v for v in items}

    def work_thumbs(self, busy_check):
        """Vorschaubilder nacheinander, nur wenn kein Render läuft."""
        while self.thumb_queue:
            if busy_check():
                return
            v = self.thumb_queue.pop(0)
            key = v["meta_key"]
            meta = self.meta.get(key, {})
            if not meta and self.has_ffprobe:
                out = run(["nice", "-n", "19", "ffprobe", "-v", "error",
                           "-select_streams", "v:0", "-show_entries",
                           "stream=width,height:format=duration", "-of",
                           "json", v["path"]], timeout=20)
                try:
                    j = json.loads(out)
                    s = j.get("streams", [{}])[0]
                    meta = {"duration": float(j["format"]["duration"]),
                            "width": s.get("width"),
                            "height": s.get("height")}
                except Exception:
                    meta = {"duration": None}
                self.meta[key] = meta
            thumb = self.thumb_dir / f"{key}.jpg"
            if not thumb.exists() and self.has_ffmpeg:
                at = min(1.0, (meta.get("duration") or 2) / 3)
                run(["nice", "-n", "19", "ffmpeg", "-y", "-v", "error",
                     "-ss", f"{at:.2f}", "-i", v["path"], "-frames:v", "1",
                     "-vf", "scale=360:-2", "-q:v", "5", str(thumb)],
                    timeout=40)
            with self.lock:
                cur = self.by_id.get(v["id"])
                if cur and cur["meta_key"] == key:
                    cur.update({k: meta.get(k) for k in ("duration", "width",
                                                         "height")})
                    cur["thumb"] = thumb.exists()
            try:
                self.meta_file.write_text(json.dumps(self.meta))
            except Exception:
                pass

    def public(self):
        with self.lock:
            return [{k: v.get(k) for k in ("id", "name", "show_path", "size",
                                           "mtime", "project", "kind",
                                           "duration", "width", "height",
                                           "thumb", "meta_key")}
                    for v in self.items]

    def get(self, vid):
        with self.lock:
            return self.by_id.get(vid)


# --------------------------------------------------------------------------
# Verlauf (GPU-Temperatur usw.)
# --------------------------------------------------------------------------

class History:
    FIELDS = ("t", "gt", "gu", "gm", "gp", "ct", "cu", "ru")

    def __init__(self, path, hours):
        self.path = path
        self.max_age = hours * 3600
        self.points = []
        self.lock = threading.Lock()
        try:
            self.points = json.loads(path.read_text())
        except Exception:
            pass

    def add(self, p):
        with self.lock:
            self.points.append(p)
            cut = time.time() - self.max_age
            while self.points and self.points[0][0] < cut:
                self.points.pop(0)

    def save(self):
        with self.lock:
            data = json.dumps(self.points, separators=(",", ":"))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(data)
        tmp.replace(self.path)

    def get(self, seconds, max_points=360):
        cut = time.time() - seconds
        with self.lock:
            pts = [p for p in self.points if p[0] >= cut]
        if len(pts) <= max_points:
            return pts
        # Zusammenfassen: Mittelwert, bei Temperatur zusätzlich Spitze
        step = len(pts) / max_points
        out = []
        for i in range(max_points):
            chunk = pts[int(i * step): int((i + 1) * step)] or \
                [pts[min(len(pts) - 1, int(i * step))]]
            row = [chunk[-1][0]]
            for j in range(1, len(self.FIELDS)):
                vals = [c[j] for c in chunk if c[j] is not None]
                if not vals:
                    row.append(None)
                elif j == 1:
                    row.append(max(vals))
                else:
                    row.append(round(sum(vals) / len(vals), 1))
            out.append(row)
        return out


# --------------------------------------------------------------------------
# Geplante Uploads (Datei data/uploads.json, von Hand oder von Claude gepflegt)
# --------------------------------------------------------------------------

def read_uploads(path, projects):
    try:
        items = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as e:
        return [{"title": f"uploads.json fehlerhaft: {e}", "error": True}]
    out = []
    now = time.time()
    for it in items if isinstance(items, list) else items.get("uploads", []):
        when = it.get("when")
        ts = None
        if isinstance(when, (int, float)):
            ts = when
        elif isinstance(when, str):
            ts = parse_time(when)
        it = dict(it)
        it["ts"] = ts
        it["project"] = it.get("project") or projects.find(it.get("title"))
        if not it.get("status"):
            it["status"] = "online" if ts and ts < now else "geplant"
        out.append(it)
    out.sort(key=lambda x: x.get("ts") or 0)
    return out


def parse_time(s):
    """'2026-11-17 18:00' (Ortszeit des Servers) oder ISO mit Zeitzone."""
    from datetime import datetime
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M%z",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000"), fmt)
            return d.timestamp()
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------
# Datensammler (echt)
# --------------------------------------------------------------------------

class Collector:
    demo = False

    def __init__(self, cfg, data_dir):
        self.cfg = cfg
        self.data_dir = data_dir
        self.projects = Projects(cfg)
        self.scanner = ProcessScanner(cfg, self.projects)
        self.cpu = CpuMeter()
        self.videos = VideoLibrary(cfg, self.projects, data_dir)
        self.history = History(data_dir / "history.json",
                               cfg["history_hours"])
        self.uploads_file = data_dir / "uploads.json"
        self.events_file = data_dir / "ereignisse.json"
        self.snapshot = {}
        self.events = self._load_events()
        self.lock = threading.Lock()
        self.heat_paused = set()
        self.gpu_error = None

    # -- Ereignis-Liste (Pausen, Hitze, Neustarts)
    def _load_events(self):
        try:
            return json.loads(self.events_file.read_text())[-200:]
        except Exception:
            return []

    def event(self, text, level="info"):
        self.events.append({"t": time.time(), "text": text, "level": level})
        self.events = self.events[-200:]
        try:
            self.events_file.write_text(json.dumps(self.events))
        except Exception:
            pass
        log("Ereignis:", text)

    def measure(self):
        gpu = read_gpu()
        self.gpu_error = None if gpu else "nvidia-smi antwortet nicht"
        cpu = {"percent": self.cpu.percent(), "temp": read_cpu_temp(),
               "cores": os.cpu_count()}
        try:
            cpu["load"] = list(os.getloadavg())
        except Exception:
            cpu["load"] = None
        procs = self.scanner.scan(gpu)
        return gpu, cpu, read_mem(), read_disks(), procs

    def collect(self):
        gpu, cpu, mem, disks, procs = self.measure()
        now = time.time()
        if gpu:
            gpu = {k: v for k, v in gpu.items() if k != "procs"}
        snap = {
            "version": VERSION,
            "demo": self.demo,
            "host": socket.gethostname(),
            "time": now,
            "boot": BOOT_TIME,
            "gpu": gpu, "gpu_error": self.gpu_error,
            "cpu": cpu, "ram": mem, "disks": disks,
            **procs,
            "uploads": read_uploads(self.uploads_file, self.projects),
            "videos": self.videos.public(),
            "projects": self.projects.public(),
            "heat_guard": dict(self.cfg["heat_guard"],
                               active=bool(self.heat_paused)),
            "events": self.events[-30:],
            "warn": self.cfg["warn"],
        }
        snap["alerts"] = self.alerts(snap)
        self.heat_guard(snap)
        with self.lock:
            self.snapshot = snap
        return snap

    def alerts(self, s):
        w = self.cfg["warn"]
        out = []
        g = s.get("gpu")
        if not g:
            out.append({"level": "bad", "text": "Grafikkarte antwortet nicht "
                        "(nvidia-smi). Bitte prüfen."})
        elif g.get("temp") is not None:
            if g["temp"] >= w["gpu_temp_bad"]:
                out.append({"level": "bad", "text": f'GPU sehr heiß: '
                            f'{g["temp"]:.0f} °C'})
            elif g["temp"] >= w["gpu_temp"]:
                out.append({"level": "warn", "text": f'GPU warm: '
                            f'{g["temp"]:.0f} °C'})
        for d in s.get("disks") or []:
            pct = 100 * d["used"] / d["total"]
            if pct >= w["disk_percent"]:
                out.append({"level": "warn", "text": f'Speicher {d["mount"]} '
                            f'zu {pct:.0f} % voll'})
        r = s.get("ram")
        if r and r["total"] and 100 * r["used"] / r["total"] >= \
                w["ram_percent"]:
            out.append({"level": "warn", "text": "Arbeitsspeicher fast voll"})
        for x in s.get("renders", []):
            if x["state"] == "pausiert":
                out.append({"level": "info", "text": f'Render pausiert: '
                            f'{x["title"]}'})
        if self.heat_paused:
            out.append({"level": "bad", "text": "Hitzewächter hat Renders "
                        "angehalten, bis die GPU abgekühlt ist."})
        return out

    def heat_guard(self, s):
        hg = self.cfg["heat_guard"]
        g = s.get("gpu") or {}
        t = g.get("temp")
        if not hg.get("enabled") or t is None:
            return
        if t >= hg["pause_at"]:
            for r in s.get("renders", []):
                if r["state"] == "läuft":
                    self.pause(r["pid"])
                    self.heat_paused.add(r["pid"])
                    self.event(f'Hitzewächter: {r["title"]} angehalten bei '
                               f'{t:.0f} °C', "bad")
        elif t <= hg["resume_at"] and self.heat_paused:
            for pid in list(self.heat_paused):
                self.resume(pid)
                self.scanner.progress.pop(pid, None)
                self.event(f"Hitzewächter: weiter bei {t:.0f} °C")
            self.heat_paused.clear()

    def history_point(self, s):
        g = s.get("gpu") or {}
        c = s.get("cpu") or {}
        r = s.get("ram") or {}
        ru = round(100 * r["used"] / r["total"], 1) if r.get("total") else None
        self.history.add([round(s["time"]), g.get("temp"), g.get("util"),
                          round(100 * g["mem_used"] / g["mem_total"], 1)
                          if g.get("mem_total") else None,
                          g.get("power"), c.get("temp"), c.get("percent"),
                          ru])

    def render_pids(self):
        with self.lock:
            return {r["pid"] for r in self.snapshot.get("renders", [])}

    def any_render(self):
        with self.lock:
            return bool(self.snapshot.get("renders"))

    def pause(self, pid):
        return signal_tree(pid, signal.SIGSTOP)

    def resume(self, pid):
        return signal_tree(pid, signal.SIGCONT)

    def video_path(self, vid):
        v = self.videos.get(vid)
        return v["path"] if v else None

    # -- Hintergrund-Schleifen
    def loop(self):
        last_hist = 0
        last_save = time.time()
        last_scan = 0
        while True:
            t0 = time.time()
            try:
                if t0 - last_scan > self.cfg["video_scan_seconds"]:
                    self.videos.scan()
                    last_scan = t0
                s = self.collect()
                if t0 - last_hist >= self.cfg["history_seconds"]:
                    self.history_point(s)
                    last_hist = t0
                if t0 - last_save > 300:
                    self.history.save()
                    last_save = t0
            except Exception:
                traceback.print_exc()
            time.sleep(max(1, self.cfg["sample_seconds"] -
                           (time.time() - t0)))

    def thumb_loop(self):
        while True:
            try:
                self.videos.work_thumbs(self.any_render)
            except Exception:
                traceback.print_exc()
            time.sleep(20)

    def start(self):
        self.videos.scan()
        self.collect()
        threading.Thread(target=self.loop, daemon=True).start()
        threading.Thread(target=self.thumb_loop, daemon=True).start()

    def stop(self):
        try:
            self.history.save()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Datensammler (Beispieldaten)
# --------------------------------------------------------------------------

class DemoCollector(Collector):
    """Spielt einen Abend auf danbds nach: ein Render läuft, zwei warten."""
    demo = True

    def __init__(self, cfg, data_dir):
        super().__init__(cfg, data_dir)
        self.t0 = time.time()
        self.paused_at = {}
        self.pause_total = {}
        self.jobs = [
            {"pid": 41237, "title": "Folge 2 · Handschlag ins Leere",
             "project": "step-three", "total": 1050, "spf": 2.6,
             "done0": 618,
             "blend": "~/kanal-2-blender/shorts/step-three-002-handshake/"
                      "szene.blend"},
        ]
        self.waiting = [
            {"pid": 41301, "title": "Folge 3 · Teacher Mom",
             "project": "step-three", "frames": 980, "ago": 900},
            {"pid": 41388, "title": "Folge 1 · Vorkoster (Endfassung)",
             "project": "shift-over", "frames": 1140, "ago": 300},
        ]
        if not self.history.points:
            self._fake_history()
        if not self.uploads_file.exists():
            self._fake_uploads()

    def _temp_at(self, t, rendering=True):
        base = 66 if rendering else 38
        return base + 5 * math.sin(t / 900) + 2 * math.sin(t / 97) + \
            random.uniform(-0.6, 0.6)

    def _fake_history(self):
        now = time.time()
        pts = []
        t = now - 24 * 3600
        while t < now:
            hour = time.localtime(t).tm_hour
            rendering = not (5 <= hour < 13)
            crash = now - 4.2 * 3600 < t < now - 3.9 * 3600
            if crash:
                t += 15
                continue
            gt = self._temp_at(t, rendering)
            if now - 4.6 * 3600 < t < now - 4.2 * 3600:
                gt += 12      # vor dem Absturz: zu heiß
            gu = (random.uniform(93, 99) if rendering else
                  random.uniform(0, 3))
            pts.append([round(t), round(gt, 1), round(gu),
                        62 if rendering else 4,
                        round(140 + random.uniform(-15, 10)) if rendering
                        else 14, round(gt - 14 + random.uniform(-2, 2), 1),
                        round(random.uniform(18, 35) if rendering else
                              random.uniform(1, 5), 1),
                        round(random.uniform(52, 61), 1)])
            t += 15
        self.history.points = pts

    def _fake_uploads(self):
        from datetime import datetime, timedelta
        today = datetime.now().replace(hour=18, minute=0, second=0,
                                       microsecond=0)
        ups = [
            {"title": "If You Say \"You Too\" to the Waiter… 😳🍽 #shorts",
             "project": "step-three", "channel": "@stepthreetips",
             "when": (today + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
             "url": "https://youtube.com/shorts/MaKD3EesQns",
             "status": "eingeplant"},
            {"title": "If Your Handshake Gets Left Hanging… 🤝😳 #shorts",
             "project": "step-three", "channel": "@stepthreetips",
             "when": (today + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
             "status": "wartet auf Render"},
            {"title": "You Taste the King's Food First… and the Soup Is "
                      "Green ☠🍲", "project": "shift-over",
             "channel": "@shiftovershorts",
             "when": (today + timedelta(days=2, hours=1)).strftime(
                 "%Y-%m-%d %H:%M"), "status": "wartet auf Freigabe"},
            {"title": "Why Your Savings Shrink While You Sleep",
             "project": "coin-island", "channel": "Coin Island",
             "when": (today - timedelta(days=1, hours=-1)).strftime(
                 "%Y-%m-%d %H:%M"), "status": "online"},
        ]
        self.uploads_file.write_text(json.dumps(ups, ensure_ascii=False,
                                                indent=2))

    def measure(self):
        now = time.time()
        rendering = any(j["pid"] not in self.paused_at for j in self.jobs)
        t = self._temp_at(now, rendering)
        gpu = {"name": "NVIDIA GeForce GTX 970", "temp": round(t),
               "util": round(random.uniform(94, 99)) if rendering else 0,
               "mem_used": 2481 if rendering else 312, "mem_total": 4096,
               "power": round(random.uniform(128, 151)) if rendering else 15,
               "power_limit": 163, "fan": 47 if rendering else 0,
               "clock": 1227 if rendering else 135}
        cpu = {"percent": round(random.uniform(19, 31), 1),
               "temp": round(t - 13), "cores": 4,
               "load": [1.42, 1.37, 1.29]}
        mem = {"total": 16 * 1024**3, "used": int(9.4 * 1024**3),
               "swap_total": 4 * 1024**3, "swap_used": 180 * 1024**2}
        disks = [{"mount": "/", "total": 468 * 1024**3,
                  "used": 301 * 1024**3}]
        renders = []
        for j in self.jobs:
            paused = j["pid"] in self.paused_at
            run_for = now - self.t0 - self.pause_total.get(j["pid"], 0)
            if paused:
                run_for -= now - self.paused_at[j["pid"]]
            done = min(j["total"], j["done0"] + int(run_for / j["spf"]))
            renders.append({
                "pid": j["pid"], "title": j["title"],
                "project": j["project"], "blend": j["blend"],
                "state": "pausiert" if paused else "läuft",
                "started": self.t0 - j["done0"] * j["spf"],
                "frame": done + 1, "start": 1, "end": j["total"],
                "done": done, "total": j["total"],
                "sec_per_frame": j["spf"],
                "eta": None if paused else
                now + (j["total"] - done) * j["spf"],
                "cpu": 24.0, "rss": int(1.9 * 1024**3),
                "gpu_mem": 2160, "last_frame": None,
                "log_tail": [f"Fra:{done + 1} Mem:812.4M | Time:00:02.61 "
                             f"| Rendering 7 / 8 samples"],
            })
        queue = [{"pid": w["pid"], "title": w["title"],
                  "project": w["project"], "blend": None,
                  "since": self.t0 - w["ago"], "frames": w["frames"]}
                 for w in self.waiting]
        sessions = [
            {"pid": 3011, "id": "cse_01AJb2KJ…St3", "project": "step-three",
             "cwd": "~/kanal-2-blender", "started": now - 3 * 3600,
             "rss": 412 * 1024**2, "cpu": 0.4, "busy": True, "children": 3},
            {"pid": 3044, "id": "cse_01AJb2KJ…ShO", "project": "shift-over",
             "cwd": "~/kanal-2-blender", "started": now - 2.4 * 3600,
             "rss": 388 * 1024**2, "cpu": 0.1, "busy": False, "children": 1},
            {"pid": 2875, "id": "cse_01Coin…a91", "project": "coin-island",
             "cwd": "~/coin-island-blender", "started": now - 26 * 3600,
             "rss": 351 * 1024**2, "cpu": 0.0, "busy": False, "children": 1},
            {"pid": 2902, "id": "cse_01Coin…c07", "project": "coin-island",
             "cwd": "~/coin-island-blender", "started": now - 25 * 3600,
             "rss": 344 * 1024**2, "cpu": 0.0, "busy": False, "children": 1},
        ]
        daemons = [{"pid": 2711, "capacity": 4, "started": now - 27 * 3600,
                    "rss": 120 * 1024**2}]
        procs = {"renders": renders, "queue": queue, "post": [],
                 "sessions": sessions, "daemons": daemons,
                 "slots": {"used": 4, "capacity": 4}}
        return gpu, cpu, mem, disks, procs

    def collect(self):
        s = super().collect()
        s["host"] = "danbds"
        s["boot"] = time.time() - 4 * 3600 - 12 * 60
        if not self.events:
            n = time.time()
            self.events = [
                {"t": n - 4.6 * 3600, "level": "bad",
                 "text": "GPU 83 °C, Bild eingefroren (Render Shift Over)"},
                {"t": n - 4.2 * 3600, "level": "bad",
                 "text": "Server nicht erreichbar"},
                {"t": n - 3.9 * 3600, "level": "info",
                 "text": "Server wieder da (Neustart)"},
                {"t": n - 3.8 * 3600, "level": "info",
                 "text": "Render Shift Over Folge 1 fortgesetzt"},
            ]
            s["events"] = self.events
        return s

    def render_pids(self):
        return {j["pid"] for j in self.jobs}

    def any_render(self):
        return False      # Vorschaubilder in der Demo sofort bauen

    def pause(self, pid):
        if pid not in self.paused_at:
            self.paused_at[pid] = time.time()
        return [pid]

    def resume(self, pid):
        if pid in self.paused_at:
            self.pause_total[pid] = self.pause_total.get(pid, 0) + \
                time.time() - self.paused_at.pop(pid)
        return [pid]


# --------------------------------------------------------------------------
# Webserver
# --------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "danbds-panel/" + VERSION
    collector = None
    cfg = None

    def log_message(self, fmt, *args):
        if "/api/status" in (args[0] if args else ""):
            return
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # -- Antworten
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False,
                          separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype, cache="no-cache", download=None):
        try:
            st = os.stat(path)
        except Exception:
            return self.send_error(404)
        size = st.st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            try:
                a, b = rng[6:].split(",")[0].split("-")
                if a == "":
                    start = max(0, size - int(b))
                else:
                    start = int(a)
                    end = int(b) if b else size - 1
                end = min(end, size - 1)
                if start > end:
                    raise ValueError
                code = 206
            except Exception:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        etag = f'"{int(st.st_mtime)}-{size}"'
        if code == 200 and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.end_headers()
            return
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        self.send_header("ETag", etag)
        if download:
            q = urllib.parse.quote(download)
            self.send_header("Content-Disposition",
                             f"attachment; filename*=UTF-8''{q}")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(256 * 1024, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self):
        ip = self.client_address[0]
        return any(ip_in(ip, n) for n in self.cfg["allowed_networks"])

    # -- Wege
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.allowed():
            return self.send_error(403, "Nur Heimnetz/Tailscale")
        url = urllib.parse.urlparse(self.path)
        p = url.path
        qs = urllib.parse.parse_qs(url.query)
        c = self.collector
        if p in ("/", "/index.html"):
            return self.send_file(HERE / "web" / "index.html",
                                  "text/html; charset=utf-8")
        if p == "/manifest.webmanifest":
            return self.send_file(HERE / "web" / "manifest.webmanifest",
                                  "application/manifest+json")
        if p in ("/icon.svg", "/icon-192.png", "/icon-512.png"):
            ctype = "image/svg+xml" if p.endswith(".svg") else "image/png"
            return self.send_file(HERE / "web" / p[1:], ctype,
                                  "max-age=86400")
        if p == "/api/status":
            with c.lock:
                snap = dict(c.snapshot)
            snap["status_page"] = self.cfg["status_page"].format(
                host=self.headers.get("Host", "localhost").split(":")[0])
            return self.send_json(snap)
        if p == "/api/history":
            rng = (qs.get("range") or ["6h"])[0]
            secs = {"1h": 3600, "6h": 6 * 3600, "24h": 86400,
                    "48h": 172800}.get(rng, 6 * 3600)
            return self.send_json({"fields": History.FIELDS,
                                   "points": c.history.get(secs)})
        m = re.match(r"^/video/([0-9a-f]{16})$", p)
        if m:
            path = c.video_path(m.group(1))
            if not path:
                return self.send_error(404)
            ext = Path(path).suffix.lower()
            ctype = {".mp4": "video/mp4", ".m4v": "video/mp4",
                     ".mov": "video/quicktime", ".webm": "video/webm",
                     ".mkv": "video/x-matroska"}.get(ext, "video/mp4")
            return self.send_file(path, ctype, "max-age=3600",
                                  Path(path).name if "dl" in qs else None)
        m = re.match(r"^/thumb/([0-9a-f]{16}-\d+-\d+)\.jpg$", p)
        if m:
            return self.send_file(c.videos.thumb_dir / f"{m.group(1)}.jpg",
                                  "image/jpeg", "max-age=604800")
        return self.send_error(404)

    def do_POST(self):
        if not self.allowed():
            return self.send_error(403)
        # Schutz gegen fremde Webseiten: nur unsere eigene Seite schickt das
        if self.headers.get("X-Panel") != "1":
            return self.send_json({"ok": False, "error": "verboten"}, 403)
        m = re.match(r"^/api/render/(\d+)/(pause|weiter)$", self.path)
        if not m:
            return self.send_error(404)
        pid, action = int(m.group(1)), m.group(2)
        c = self.collector
        if pid not in c.render_pids():
            return self.send_json({"ok": False, "error":
                                   "Kein laufender Render mit dieser Nummer"},
                                  404)
        if action == "pause":
            hit = c.pause(pid)
            c.event(f"Render angehalten (von Hand, PID {pid})")
        else:
            hit = c.resume(pid)
            c.heat_paused.discard(pid)
            c.scanner.progress.pop(pid, None)   # Pause nicht in Tempo zählen
            c.event(f"Render fortgesetzt (von Hand, PID {pid})")
        c.collect()
        return self.send_json({"ok": True, "pids": hit})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        if ":" in self.server_address[0]:
            self.address_family = socket.AF_INET6
            self.socket = socket.socket(self.address_family, self.socket_type)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser(description="danbds Admin-Panel")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--demo", action="store_true",
                    help="Beispieldaten statt echter Werte")
    ap.add_argument("--port", type=int)
    ap.add_argument("--host")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.port:
        cfg["port"] = args.port
    if args.host:
        cfg["host"] = args.host
    data_dir = HERE / cfg["data_dir"]
    if args.demo:
        data_dir = HERE / "demo-data"
        cfg["videos"] = [{"dir": str(HERE / "demo-data" / "videos"),
                          "recursive": True}]
    data_dir.mkdir(parents=True, exist_ok=True)

    collector = (DemoCollector if args.demo else Collector)(cfg, data_dir)
    collector.start()
    Handler.collector = collector
    Handler.cfg = cfg

    srv = Server((cfg["host"], cfg["port"]), Handler)

    def bye(*_):
        collector.stop()
        os._exit(0)
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    log(f'Admin-Panel läuft: http://{cfg["host"]}:{cfg["port"]}/'
        + ("  (BEISPIELDATEN)" if args.demo else ""))
    srv.serve_forever()


if __name__ == "__main__":
    main()
