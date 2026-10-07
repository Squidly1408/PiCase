#!/usr/bin/env python3
"""
console.py - full-screen dashboard for the briefcase monitor.

Shows the network uplink (wired / Wi-Fi), internet reachability, and a live
table of every backplane slot. Keys:

  Up/Down  select a slot        i  identify (blink LED)
  r        reboot node          s  shut down node
  w        Wi-Fi / network setup (nmtui)
  P        power off the whole case
  x        exit to a shell      q  quit
"""

from __future__ import annotations

import curses
import json
import os
import socket
import subprocess
import time

SOCKET_PATH = os.environ.get("PICASE_SOCKET", "/run/picase/master.sock")


def call(req: dict) -> dict:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(SOCKET_PATH)
            s.sendall((json.dumps(req) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "nodes": [], "events": []}


def uplink_status() -> list[str]:
    """One line per interface the controller cares about."""
    lines = []
    try:
        out = subprocess.run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"],
                             capture_output=True, text=True, timeout=2).stdout
        for row in out.splitlines():
            dev, typ, state, conn = (row.split(":") + ["", "", "", ""])[:4]
            if typ in ("ethernet", "wifi"):
                role = {"eth0": "internal LAN", "eth1": "wired uplink",
                        "wlan0": "Wi-Fi uplink"}.get(dev, typ)
                lines.append(f"{dev:<6} {role:<13} {state:<14} {conn}")
    except (OSError, subprocess.SubprocessError):
        lines.append("nmcli not available")
    return lines


_net_cache = {"t": 0.0, "ok": False}


def internet_ok() -> bool:
    if time.time() - _net_cache["t"] > 10:
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
            _net_cache["ok"] = True
        except OSError:
            _net_cache["ok"] = False
        _net_cache["t"] = time.time()
    return _net_cache["ok"]


def draw(stdscr, state: dict, sel: int, msg: str) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    GREEN, RED, YEL, DIM, HEAD = (curses.color_pair(i) for i in range(1, 6))

    def put(y, x, text, attr=0):
        if 0 <= y < h:
            try:
                stdscr.addnstr(y, x, text, max(0, w - x - 1), attr)
            except curses.error:
                pass

    put(0, 0, " PiCase Portable Cluster ".ljust(w - 1), HEAD | curses.A_BOLD)
    put(0, w - 22, time.strftime(" %a %d %b %H:%M:%S "), HEAD)

    y = 2
    net = internet_ok()
    put(y, 1, "Internet: ", curses.A_BOLD)
    put(y, 11, "reachable" if net else "NOT reachable", GREEN if net else RED)
    for line in uplink_status():
        y += 1
        put(y, 3, line, GREEN if " connected " in f" {line} " else DIM)

    y += 2
    put(y, 1, f"{'SLOT':<6}{'HOST':<16}{'IP':<15}{'TEMP':>6}{'CPU%':>6}{'MEM%':>6}"
              f"{'DISK%':>7}  POWER", curses.A_BOLD | curses.A_UNDERLINE)
    nodes = state.get("nodes", [])
    for idx, n in enumerate(nodes):
        y += 1
        i, s = n["info"], n["stats"]
        if n["online"]:
            thr = s.get("thr", "-")
            pw_ok = thr in ("0x0", "n/a", "-")
            def num(v):
                return f"{v:.0f}" if isinstance(v, (int, float)) else "-"
            row = (f"{n['slot']:02d}    {i.get('h', '?')[:15]:<16}{i.get('ip', '-'):<15}"
                   f"{num(s.get('t')):>6}{num(s.get('c')):>6}{num(s.get('mu')):>6}"
                   f"{num(s.get('du')):>7}  {'ok' if pw_ok else 'WARN ' + thr}")
            hot = isinstance(s.get("t"), (int, float)) and s["t"] >= 75
            attr = RED if (hot or not pw_ok) else GREEN
        elif i:
            row, attr = f"{n['slot']:02d}    {i.get('h', '?')[:15]:<16}OFFLINE", RED
        else:
            row, attr = f"{n['slot']:02d}    -- empty --", DIM
        if idx == sel:
            attr |= curses.A_REVERSE
        put(y, 1, row.ljust(min(w - 3, 80)), attr)

    y += 2
    put(y, 1, "Recent events", curses.A_BOLD)
    for ev in state.get("events", [])[-(h - y - 4):]:
        y += 1
        put(y, 3, ev, DIM)

    y = min(y, h - 4)
    if not state.get("ok", True):
        put(h - 3, 1, f"Bus master not reachable: {state.get('error')}", RED | curses.A_BOLD)
    put(h - 2, 1, msg, YEL)
    put(h - 1, 0, " ↑↓ select  i identify  r reboot  s shutdown  w net  "
                  "P power-off  x shell  q quit ".ljust(w - 1)[:w - 1], HEAD)
    stdscr.refresh()


def confirm(stdscr, question: str) -> bool:
    h, w = stdscr.getmaxyx()
    stdscr.addnstr(h - 2, 1, (question + " [y/N] ").ljust(w - 2), w - 2,
                   curses.color_pair(3) | curses.A_BOLD)
    stdscr.nodelay(False)
    ch = stdscr.getch()
    stdscr.nodelay(True)
    return ch in (ord("y"), ord("Y"))


def main(stdscr) -> str:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
    stdscr.nodelay(True)
    sel, msg, last = 0, "", 0.0
    state: dict = {}
    while True:
        if time.time() - last > 1.0:
            state, last = call({"cmd": "status"}), time.time()
        nodes = state.get("nodes", [])
        sel = max(0, min(sel, len(nodes) - 1))
        draw(stdscr, state, sel, msg)
        ch = stdscr.getch()
        if ch == -1:
            time.sleep(0.05)
            continue
        slot = nodes[sel]["slot"] if nodes else None
        if ch in (ord("q"), 27):
            return "quit"
        if ch == ord("x"):
            return "shell"
        if ch == curses.KEY_UP:
            sel -= 1
        elif ch == curses.KEY_DOWN:
            sel += 1
        elif ch == ord("i") and slot:
            r = call({"cmd": "identify", "slot": slot, "secs": 10})
            msg = f"identify slot {slot}: {r.get('results', r.get('error'))}"
        elif ch in (ord("r"), ord("s")) and slot:
            action = "reboot" if ch == ord("r") else "shutdown"
            if confirm(stdscr, f"{action} slot {slot}?"):
                r = call({"cmd": action, "slot": slot})
                msg = f"{action} slot {slot}: {r.get('results', r.get('error'))}"
        elif ch == ord("w"):
            curses.endwin()
            subprocess.run(["sudo", "nmtui"])
            stdscr.refresh()
        elif ch == ord("P"):
            if confirm(stdscr, "Power off ALL nodes and the controller?"):
                curses.endwin()
                subprocess.run(["casectl", "poweroff-case", "--yes"])
                return "quit"
        last = 0 if ch in (ord("i"), ord("r"), ord("s")) else last


if __name__ == "__main__":
    result = curses.wrapper(main)
    if result == "shell":
        print("Type `picase-console` to return to the dashboard.")
