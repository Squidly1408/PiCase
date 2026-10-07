#!/usr/bin/env python3
"""Generates every diagram in this folder as SVG + PNG.
   python3 make_diagrams.py        (PNG export needs: pip install cairosvg)"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))
INK = "#1d2733"; MUTED = "#5b6775"; LINE = "#9aa5b1"; PAPER = "#ffffff"; PANEL = "#f2f4f7"
TEAL = "#0e8f84"; TEAL_L = "#d6f0ed"; AMBER = "#d98a1c"; AMBER_L = "#fbecd3"
BLUE = "#2f64d6"; BLUE_L = "#dde7fb"; RED = "#cc3b3b"; RED_L = "#f9dddd"
GREEN = "#2e9d4f"; GREEN_L = "#dcf2e2"; PCB = "#1f7a4d"; PCB_L = "#cfe8da"
FONT = "Inter, 'DejaVu Sans', Arial, sans-serif"
MONO = "'DejaVu Sans Mono', monospace"


def svg(w, h, body, title):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<title>{title}</title>
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>
  <marker id="arrT" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{TEAL}"/></marker>
  <marker id="arrA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{AMBER}"/></marker>
  <marker id="dot" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6"><circle cx="5" cy="5" r="4" fill="{INK}"/></marker>
  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0 L0 0 0 20" fill="none" stroke="#eef1f4" stroke-width="1"/></pattern>
  <pattern id="vent" width="12" height="12" patternUnits="userSpaceOnUse"><rect width="12" height="12" fill="#3a4552"/><rect x="2" y="3" width="8" height="2" rx="1" fill="#1b232c"/><rect x="2" y="8" width="8" height="2" rx="1" fill="#1b232c"/></pattern>
</defs>
<rect width="{w}" height="{h}" fill="{PAPER}"/>
{body}
</svg>"""


def R(x, y, w, h, fill=PANEL, stroke=INK, sw=1.5, rx=6, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def T(x, y, s, size=14, weight=400, anchor="start", fill=INK, family=None, extra=""):
    fam = f' font-family="{family}"' if family else ""
    if family == MONO:
        s = s.replace(" ", "&#160;")
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{fill}"{fam} {extra}>{s}</text>')


def L(x1, y1, x2, y2, stroke=INK, sw=1.5, extra=""):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def P(d, stroke=INK, sw=1.5, fill="none", extra=""):
    return f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" fill="{fill}" {extra}/>'


def badge(x, y, n, fill=TEAL):
    return (f'<circle cx="{x}" cy="{y}" r="12" fill="{fill}"/>'
            + T(x, y + 4.5, n, 13, 700, "middle", "#fff"))


def heading(w, title, sub):
    return (T(40, 48, title, 26, 700) + T(40, 74, sub, 15, 400, fill=MUTED)
            + L(40, 90, w - 40, 90, LINE, 1))


# ---------------------------------------------------------------------------
# 1. Briefcase overview (oblique view, lid open)
# ---------------------------------------------------------------------------
def briefcase():
    W, H = 1600, 900
    b = [heading(W, "PiCase - briefcase overview", "Lid open, ready to use. Everything runs from the briefcase; plug in power and go.")]
    ox, oy = 60, 70
    # Lid (parallelogram) with monitor - drawn in local coords via matrix
    b.append(f'<g transform="translate({ox},{oy})">')
    b.append(f'<polygon points="270,350 1170,350 1200,40 300,40" fill="#2b3440" stroke="{INK}" stroke-width="2"/>')
    b.append('<g transform="matrix(1,0,-0.0968,1,300,40)">')
    b.append(R(40, 22, 820, 266, "#0b1117", "#000", 2, 8))
    b.append(R(52, 32, 796, 246, "#0f1a22", "none", 0, 3))
    # tiny dashboard on screen
    b.append(R(52, 32, 796, 22, "#1aa3a0", "none", 0, 0))
    b.append(T(64, 48, "PiCase Portable Cluster", 13, 700, fill="#06201f", family=MONO))
    b.append(T(836, 48, "Thu 10:42", 12, 400, "end", "#06201f", MONO))
    b.append(T(64, 76, "Internet: reachable   eth1 wired uplink  connected", 12, 400, fill="#7ee08f", family=MONO))
    b.append(T(64, 94, "                      wlan0 Wi-Fi uplink standby", 12, 400, fill="#7c8a96", family=MONO))
    b.append(T(64, 120, "SLOT HOST           IP           TEMP CPU% POWER", 12, 700, fill="#d7dee5", family=MONO))
    rows = [("01", "picase-node01", "10.42.0.31", "48", "12", "ok"),
            ("02", "picase-node02", "10.42.0.44", "51", "37", "ok"),
            ("03", "picase-node03", "10.42.0.58", "46", "8", "ok"),
            ("04", "-- empty --", "", "", "", "")]
    for i, r in enumerate(rows):
        col = "#7ee08f" if r[2] else "#56636f"
        b.append(T(64, 140 + i * 18, f"{r[0]:<5}{r[1]:<15}{r[2]:<13}{r[3]:>4}{r[4]:>5} {r[5]}".replace(" ", "&#160;"),
                   12, 400, fill=col, family=MONO))
    b.append(T(64, 230, "10:41:07 slot 03 joined: picase-node03", 12, 400, fill="#7c8a96", family=MONO))
    b.append(R(52, 256, 796, 22, "#1aa3a0", "none", 0, 0))
    b.append(T(64, 272, "i identify  r reboot  s shutdown  w net  q quit", 12, 400, fill="#06201f", family=MONO))
    b.append('</g>')
    # Base top face
    b.append(f'<polygon points="150,520 1050,520 1170,350 270,350" fill="#3a4552" stroke="{INK}" stroke-width="2"/>')
    b.append('<g transform="matrix(1,0,-0.7059,1,270,350)">')
    # hinged deck outline
    b.append(R(14, 10, 620, 150, "#46525f", "#202830", 1.5, 6))
    # keyboard
    b.append(R(40, 22, 470, 124, "#1c232b", "#0d1116", 1.5, 6))
    keys_rows = [(14, 28), (14, 28), (13, 28), (12, 28)]
    for r, (n, kw) in enumerate(keys_rows):
        x0 = 50 + r * 8
        for k in range(n):
            b.append(R(x0 + k * 32, 30 + r * 22, kw, 17, "#e9edf1", "none", 0, 3))
    b.append(R(130, 30 + 4 * 22, 230, 17, "#e9edf1", "none", 0, 3))
    # touchpad
    b.append(R(522, 32, 100, 104, "#27303a", "#0d1116", 1.5, 8))
    # deck vents + hinge
    b.append(R(14, 150, 620, 6, "#202830", "none", 0, 2))
    # right area: status LEDs + vent
    b.append(R(650, 10, 236, 150, "#2f3944", "#202830", 1.5, 6))
    for i in range(8):
        col = [GREEN, GREEN, GREEN, GREEN, "#56636f", "#56636f", "#56636f", "#56636f"][i]
        b.append(f'<circle cx="{672 + i * 26}" cy="34" r="7" fill="{col}" stroke="#111" stroke-width="1"/>')
    b.append(R(668, 58, 200, 90, "url(#vent)", "#202830", 1, 4))
    b.append('</g>')
    # Base front face + right face
    b.append(f'<polygon points="150,520 1050,520 1050,640 150,640" fill="#2b3440" stroke="{INK}" stroke-width="2"/>')
    b.append(f'<polygon points="1050,520 1170,350 1170,470 1050,640" fill="#222a33" stroke="{INK}" stroke-width="2"/>')
    # front handle + latches
    b.append(R(500, 548, 200, 26, "#1a2027", "#0d1116", 2, 13))
    b.append(R(230, 540, 60, 36, "#9aa5b1", "#4a5561", 1.5, 4))
    b.append(R(910, 540, 60, 36, "#9aa5b1", "#4a5561", 1.5, 4))
    # right-face I/O panel (local coords)
    b.append('<g transform="matrix(0.7059,-1,0,1,1050,520)">')
    b.append(R(14, 14, 142, 92, "#333d48", "#11161b", 1.2, 4))
    b.append(f'<circle cx="34" cy="40" r="9" fill="#111" stroke="#9aa5b1" stroke-width="2"/>')        # DC jack
    b.append(R(56, 30, 22, 22, RED, "#111", 1.2, 3))                                               # power switch
    b.append(R(90, 30, 26, 22, "#111", "#9aa5b1", 1.5, 2))                                          # RJ45
    b.append(R(124, 32, 22, 10, "#111", "#9aa5b1", 1.5, 1))                                         # USB
    b.append(R(124, 46, 22, 10, "#111", "#9aa5b1", 1.5, 1))
    b.append(f'<circle cx="40" cy="80" r="6" fill="#c9a227" stroke="#111"/>')                        # SMA
    b.append('</g>')
    # antenna
    b.append(P("M1078,500 L1098,410", "#1a2027", 7, extra='stroke-linecap="round"'))
    b.append('</g>')

    # callouts: (badge x,y) -> target point
    def call(n, bx, by, tx, ty, label, sub):
        tx, ty = tx + ox, ty + oy
        anchor = "start" if bx < W / 2 else "start"
        out = [P(f"M{bx},{by} L{tx},{ty}", MUTED, 1.2, extra='marker-end="url(#dot)"'), badge(bx, by, n)]
        tx_label = bx + 20
        out.append(T(tx_label, by + 5, label, 15, 700, anchor))
        out.append(T(tx_label, by + 24, sub, 13, 400, anchor, MUTED))
        return "".join(out)

    b.append(call(1, 1340, 150, 1150, 140, "13.3\" HDMI monitor", "in the lid, cabled to slot 0"))
    b.append(call(2, 40, 730, 420, 450, "Keyboard + touchpad", "on the hinged deck"))
    b.append(call(3, 40, 800, 330, 512, "Hinged deck", "lifts to reach the Pi bay"))
    b.append(call(4, 420, 800, 905, 380, "Slot LEDs", "one per Pi - blink = identify"))
    b.append(call(5, 760, 800, 950, 450, "Air vents", "fan exhaust from the Pi bay"))
    b.append(call(6, 1340, 520, 1110, 540, "Side I/O panel", "12 V in, power switch, RJ45, USB"))
    b.append(call(7, 1340, 380, 1155, 440, "Wi-Fi antenna", "USB Wi-Fi on the controller"))
    b.append(call(8, 1120, 800, 600, 630, "Carry handle", "case closes over everything"))
    return svg(W, H, "".join(b), "PiCase briefcase overview")


# ---------------------------------------------------------------------------
# 2. Internal layout (top-down, to scale 2 px / mm)
# ---------------------------------------------------------------------------
def layout():
    W, H = 1440, 980
    S = 2.0
    X0, Y0 = 70, 150
    def mm(x, y):
        return X0 + x * S, Y0 + y * S
    b = [heading(W, "Internal layout - base of the case (top view)", "Drawn to scale, 2 px = 1 mm. Example case: 460 x 330 mm inside, 120 mm deep base. Hinged deck removed.")]
    # case
    b.append(R(X0 - 14, Y0 - 14, 460 * S + 28, 330 * S + 28, "#2b3440", INK, 2, 22))
    b.append(R(X0, Y0, 460 * S, 330 * S, "url(#grid)", "#55616e", 1.5, 10))
    b.append(T(X0 + 230 * S, Y0 - 24, "BACK (hinge side)", 13, 700, "middle", MUTED))
    b.append(T(X0 + 230 * S, Y0 + 330 * S + 34, "FRONT (handle side)", 13, 700, "middle", MUTED))
    # dimension lines
    b.append(L(X0, Y0 + 330 * S + 50, X0 + 460 * S, Y0 + 330 * S + 50, MUTED, 1, 'marker-start="url(#arr)" marker-end="url(#arr)"'))
    b.append(T(X0 + 230 * S, Y0 + 330 * S + 68, "460 mm", 13, 400, "middle", MUTED))

    # backplane
    x, y = mm(12, 18)
    b.append(R(x, y, 276 * S, 132 * S, PCB_L, PCB, 2, 6))
    bp_label = (R(x + 4, y + 132 * S - 28, 290, 22, PCB_L, "none", 0, 4)
                + T(x + 10, y + 132 * S - 12, "BACKPLANE PCB (8 slots, 30 mm pitch)", 13, 700, fill=PCB))
    # rear fans
    for fx in (60, 180):
        cx, cy = mm(fx, 6)
        b.append(R(cx - 60, cy - 10, 120, 20, "#3a4552", INK, 1.2, 4))
        b.append(T(cx, cy + 5, "60 mm fan", 11, 700, "middle", "#fff"))
        b.append(L(cx, cy + 14, cx, cy + 56, TEAL, 2, 'marker-end="url(#arrT)"'))
    # blades
    for s in range(8):
        bx = 26 + s * 30
        x1, y1 = mm(bx, 26)
        # Pi blade (seen edge-on): 85 mm long, ~20 mm incl. cooler
        b.append(R(x1, y1, 18 * S, 85 * S, "#e7ece9" if s else BLUE_L, PCB if s else BLUE, 1.6, 3))
        b.append(R(x1 + 2 * S, y1 + 14 * S, 5 * S, 52 * S, "#222", "none", 0, 1))           # GPIO header
        b.append(R(x1 + 2 * S, y1 + 72 * S, 14 * S, 13 * S, "#b8c0c8", INK, 1, 1))         # RJ45 on front
        b.append(T(x1 + 9 * S, y1 - 6, f"{s}", 13, 700, "middle", BLUE if s == 0 else INK))
        # per-slot strip: switch, fuse, transceiver, LED
        sx, sy = mm(bx - 2, 116)
        b.append(R(sx, sy, 22 * S, 9 * S, AMBER_L, AMBER, 1, 2))             # RS-485 module
        b.append(R(sx + 4, sy + 20, 10, 10, RED, INK, 1, 2))                  # slot switch
        b.append(f'<circle cx="{sx + 30}" cy="{sy + 25}" r="4" fill="{GREEN}"/>')
        b.append(R(sx + 22 * S - 14, sy + 20, 10, 10, "#f0c75e", INK, 1, 5))  # PTC fuse
    # card guides
    x, y = mm(20, 22)
    b.append(R(x, y, 252 * S, 4 * S, "#9aa5b1", "none", 0, 2))
    b.append(T(x + 252 * S - 4, y - 4, "card guide", 11, 600, "end", "#fff"))
    # switch
    sx, sy = mm(40, 175)
    b.append(R(sx, sy, 160 * S, 95 * S, "#dfe4ea", INK, 2, 8))
    b.append(T(sx + 80 * S, sy + 58 * S, "8-port Gigabit switch", 16, 700, "middle"))
    b.append(T(sx + 80 * S, sy + 72 * S, "unmanaged, 5 V or 12 V input", 13, 400, "middle", MUTED))
    for p in range(8):
        px = sx + 12 * S + p * 18 * S
        b.append(R(px, sy + 6, 14 * S, 12 * S, "#222", "#666", 1, 2))
        # patch cable from blade RJ45 (front edge y=111mm) to port
        bx = 26 + p * 30
        cx1, cy1 = mm(bx + 9, 111)
        b.append(P(f"M{cx1},{cy1} C{cx1},{cy1 + 60} {px + 14},{sy - 60} {px + 14},{sy + 6}",
                   BLUE if p == 0 else "#4d84e8", 3, extra='opacity="0.85"'))
    # power section
    px, py = mm(312, 20)
    b.append(R(px, py, 140 * S, 300 * S, "#fff6ea", AMBER, 1.5, 8, 'stroke-dasharray="6 4"'))
    b.append(T(px + 10, py + 22, "POWER BAY", 13, 700, fill=AMBER))
    bx1, by1 = mm(330, 60)
    b.append(R(bx1, by1, 90 * S, 50 * S, "#ffe6bf", INK, 1.5, 6))
    b.append(T(bx1 + 90, by1 + 44, "Buck A", 15, 700, "middle"))
    b.append(T(bx1 + 90, by1 + 64, "12 V → 5.1 V 15 A", 12, 400, "middle", MUTED))
    b.append(T(bx1 + 90, by1 + 80, "slots 0-3", 12, 400, "middle", MUTED))
    bx2, by2 = mm(330, 125)
    b.append(R(bx2, by2, 90 * S, 50 * S, "#ffe6bf", INK, 1.5, 6))
    b.append(T(bx2 + 90, by2 + 44, "Buck B", 15, 700, "middle"))
    b.append(T(bx2 + 90, by2 + 64, "12 V → 5.1 V 15 A", 12, 400, "middle", MUTED))
    b.append(T(bx2 + 90, by2 + 80, "slots 4-7", 12, 400, "middle", MUTED))
    fx, fy = mm(330, 195)
    b.append(R(fx, fy, 90 * S, 30 * S, "#f6dede", INK, 1.5, 6))
    b.append(T(fx + 90, fy + 26, "12 V fuse block", 13, 700, "middle"))
    b.append(T(fx + 90, fy + 44, "20 A main + small fuses", 11, 400, "middle", MUTED))
    mx, my = mm(330, 240)
    b.append(R(mx, my, 90 * S, 26 * S, "#eef", INK, 1.5, 6))
    b.append(T(mx + 90, my + 22, "12 V → USB-C PD", 12, 700, "middle"))
    b.append(T(mx + 90, my + 38, "for the lid monitor", 11, 400, "middle", MUTED))
    # 5 V feed to backplane
    b.append(P(f"M{bx1},{by1 + 50} L{mm(288, 70)[0]},{by1 + 50}", RED, 4))
    b.append(P(f"M{bx2},{by2 + 50} L{mm(288, 70)[0]},{by2 + 50}", RED, 4))
    # side panel (right wall)
    wx = X0 + 460 * S
    items = [("12 V in (XT60)", 40, "#111"), ("Power switch", 75, RED), ("RJ45 uplink", 110, "#111"),
             ("USB-A x2", 145, "#111"), ("Wi-Fi antenna", 180, "#c9a227")]
    for label, ymm, col in items:
        yy = Y0 + ymm * S
        b.append(R(wx - 6, yy - 10, 18, 20, col, INK, 1.2, 3))
        b.append(L(wx + 12, yy, wx + 40, yy, MUTED, 1))
        b.append(T(wx + 46, yy + 5, label, 13, 600))
    b.append(T(wx + 46, Y0 + 20 * S, "RIGHT-SIDE I/O PANEL", 12, 700, fill=MUTED))
    # controller extras
    cx, cy = mm(215, 185)
    b.append(R(cx, cy, 85 * S, 70 * S, BLUE_L, BLUE, 1.5, 8))
    b.append(T(cx + 85, cy + 22, "Controller extras", 13, 700, "middle", BLUE))
    for i, s in enumerate(["USB-Ethernet (eth1)", "  → side RJ45", "USB Wi-Fi + antenna",
                           "HDMI → lid monitor", "USB → keyboard"]):
        b.append(T(cx + 12, cy + 44 + i * 19, s, 12, 400))
    # airflow note
    b.append(bp_label)
    ax, ay = mm(20, 292)
    b.append(T(ax, ay, "Airflow: rear fans blow along the gaps between blades,", 13, 600, fill="#bfeee8"))
    b.append(T(ax, ay + 18, "then out through the deck vents and front vents.", 13, 600, fill="#bfeee8"))
    # legend
    lx, ly = 70, Y0 + 330 * S + 100
    leg = [(BLUE_L, BLUE, "Slot 0 - controller Pi"), ("#e7ece9", PCB, "Slots 1-7 - worker Pis (blades)"),
           (AMBER_L, AMBER, "RS-485 transceiver per slot"), (RED, INK, "Per-slot power switch"),
           ("#f0c75e", INK, "3 A PTC fuse per slot")]
    for i, (f, s, t) in enumerate(leg):
        xx = lx + i * 262
        b.append(R(xx, ly - 12, 18, 14, f, s, 1.2, 3))
        b.append(T(xx + 26, ly, t, 13))
    return svg(W, H, "".join(b), "PiCase internal layout")


# ---------------------------------------------------------------------------
# 3. Network topology
# ---------------------------------------------------------------------------
def network():
    W, H = 1400, 860
    b = [heading(W, "Network design", "The controller is the only Pi that talks to the outside world. Workers sit on a private LAN behind it.")]
    # outside
    b.append(P("M90,330 q-40,0 -40,-35 q0,-38 45,-38 q12,-38 60,-32 q35,-30 75,5 q45,0 45,38 q0,62 -50,62 z",
               INK, 1.8, "#eef3fb"))
    b.append(T(150, 310, "Internet", 17, 700, "middle"))
    b.append(R(40, 430, 220, 74, BLUE_L, BLUE, 1.5, 10))
    b.append(T(150, 462, "Wi-Fi network", 15, 700, "middle"))
    b.append(T(150, 484, "hotspot, venue, home", 12, 400, "middle", MUTED))
    b.append(R(40, 540, 220, 74, "#e8ebef", INK, 1.5, 10))
    b.append(T(150, 572, "Wired network", 15, 700, "middle"))
    b.append(T(150, 594, "any LAN wall socket", 12, 400, "middle", MUTED))
    b.append(L(150, 360, 150, 428, INK, 1.5, 'marker-start="url(#arr)"'))
    b.append(P("M262,577 L280,577 L280,360 L200,350", INK, 1.5, extra='marker-end="url(#arr)"'))
    # briefcase boundary
    b.append(R(330, 120, 1040, 700, "none", MUTED, 2, 18, 'stroke-dasharray="10 6"'))
    b.append(T(350, 148, "INSIDE THE BRIEFCASE", 13, 700, fill=MUTED))
    # controller
    b.append(R(400, 330, 330, 300, BLUE_L, BLUE, 2, 12))
    b.append(T(565, 362, "Controller Pi - slot 0", 17, 700, "middle"))
    b.append(T(565, 384, "keyboard + monitor attached", 12, 400, "middle", MUTED))
    ifs = [("wlan0", "Wi-Fi uplink", "DHCP client · route metric 600", 420),
           ("eth1", "Wired uplink (USB adapter)", "behind side RJ45 · metric 100", 490),
           ("eth0", "Internal LAN 10.42.0.1/24", "DHCP server + DNS + NAT", 560)]
    for name, role, sub, y in ifs:
        b.append(R(418, y - 18, 294, 56, "#fff", BLUE, 1.2, 8))
        b.append(T(432, y + 4, name, 14, 700, family=MONO, fill=BLUE))
        b.append(T(500, y + 4, role, 13, 700))
        b.append(T(500, y + 24, sub, 12, 400, fill=MUTED))
    b.append(P("M262,467 L360,467 L360,440 L416,440", BLUE, 2, extra='marker-end="url(#arr)"'))
    b.append(P("M262,577 L330,577 L380,510 L416,510", INK, 2, extra='marker-end="url(#arr)"'))
    b.append(T(300, 455, "Wi-Fi", 12, 600, fill=BLUE))
    b.append(T(338, 600, "side RJ45", 12, 600))
    # switch
    b.append(R(800, 545, 180, 70, "#dfe4ea", INK, 2, 10))
    b.append(T(890, 576, "8-port switch", 15, 700, "middle"))
    b.append(T(890, 596, "Gigabit, unmanaged", 12, 400, "middle", MUTED))
    b.append(L(712, 580, 798, 580, BLUE, 3, 'marker-end="url(#arr)"'))
    # workers
    for i in range(7):
        y = 172 + i * 72
        b.append(R(1080, y, 250, 56, "#eef6f1", PCB, 1.5, 8))
        b.append(T(1096, y + 24, f"picase-node{i + 1:02d}", 14, 700, family=MONO))
        b.append(T(1096, y + 44, f"slot {i + 1} · 10.42.0.x (DHCP)", 12, 400, fill=MUTED))
        b.append(P(f"M980,580 C1030,580 1030,{y + 28} 1078,{y + 28}", "#4d84e8", 2))
    # management bus
    b.append(R(400, 700, 960, 60, AMBER_L, AMBER, 1.5, 10))
    b.append(T(420, 726, "RS-485 management bus on the GPIO backplane", 15, 700, fill="#8a5508"))
    b.append(T(420, 746, "slot discovery · health &amp; temps · identify · reboot / shutdown · works even if Ethernet is down", 12, 400, fill="#8a5508"))
    b.append(L(565, 630, 565, 698, AMBER, 3, 'stroke-dasharray="6 4"'))
    b.append(L(1345, 200, 1345, 698, AMBER, 3, 'stroke-dasharray="6 4"'))
    for i in range(7):
        y = 200 + i * 72
        b.append(L(1330, y, 1345, y, AMBER, 3))
    # rules box
    b.append(R(400, 160, 600, 140, "#fff", LINE, 1.2, 10))
    b.append(T(420, 188, "How traffic flows", 15, 700))
    for i, s in enumerate(["Cable in the side RJ45? → it wins (metric 100). Otherwise Wi-Fi.",
                           "Workers get 10.42.0.x from the controller and reach the",
                           "internet through it (NAT). They never use their own Wi-Fi.",
                           "Hostnames picase-node01..07 are kept in /etc/hosts."]):
        b.append(T(420, 214 + i * 21, s, 13, 400, fill=MUTED))
    return svg(W, H, "".join(b), "PiCase network design")


# ---------------------------------------------------------------------------
# 4. Backplane wiring - one slot + shared rails
# ---------------------------------------------------------------------------
def backplane():
    W, H = 1440, 960
    b = [heading(W, "Backplane wiring - one slot (repeat for every slot)", "Each Pi plugs into a right-angle 2x20 female header. Shared rails run the length of the backplane.")]
    # Pi header block
    b.append(R(60, 150, 260, 600, BLUE_L, BLUE, 2, 12))
    b.append(T(190, 180, "Raspberry Pi", 17, 700, "middle"))
    b.append(T(190, 200, "40-pin header (used pins)", 12, 400, "middle", MUTED))
    pins = [("2, 4", "5V in", 250, RED), ("6, 9, 14, 20, 25,", "GND", 300, INK), ("30, 34, 39", "", 318, INK),
            ("1", "3V3 out", 370, "#a05a00"), ("8", "GPIO14 TXD", 420, AMBER), ("10", "GPIO15 RXD", 470, AMBER),
            ("11", "GPIO17 DE/RE", 520, AMBER), ("29 31 33 35", "GPIO5/6/13/19", 590, TEAL),
            ("37", "GPIO26 LED", 680, GREEN)]
    for pin, name, y, col in pins:
        if pin:
            b.append(T(80, y + 5, f"pin {pin}", 12, 600, fill=MUTED, family=MONO))
        if name:
            b.append(T(300, y + 5, name, 13, 700, "end", col))
            b.append(f'<circle cx="320" cy="{y}" r="5" fill="{col}"/>')
    # rails on right
    rails = [("5V rail (from buck converter)", 230, RED), ("GND rail", 300, INK),
             ("RS-485  A", 820, AMBER), ("RS-485  B", 860, AMBER)]
    for name, y, col in rails:
        b.append(L(980, y, 1400, y, col, 5 if "5V" in name or "GND" in name else 3))
        b.append(T(1400, y - 10, name, 13, 700, "end", col))
    # 5V path: pin -> PTC -> switch -> 5V rail
    b.append(L(320, 250, 440, 250, RED, 3))
    b.append(R(440, 232, 90, 36, "#f0c75e", INK, 1.5, 18))
    b.append(T(485, 255, "PTC 3 A", 12, 700, "middle"))
    b.append(L(530, 250, 620, 250, RED, 3))
    b.append(R(620, 230, 110, 40, RED_L, RED, 1.5, 6))
    b.append(T(675, 255, "slot switch", 12, 700, "middle", RED))
    b.append(P("M730,250 L860,250 L860,230 L980,230", RED, 3))
    b.append(f'<circle cx="980" cy="230" r="6" fill="{RED}"/>')
    b.append(T(560, 216, "per-slot power so you can add a Pi while the rest keep running", 12, 400, fill=MUTED))
    # GND
    b.append(L(320, 300, 980, 300, INK, 3))
    b.append(f'<circle cx="980" cy="300" r="6" fill="{INK}"/>')
    # transceiver
    tx, ty = 560, 360
    b.append(R(tx, ty, 240, 260, AMBER_L, AMBER, 2, 10))
    b.append(T(tx + 140, ty + 30, "3.3 V RS-485", 16, 700, "middle", "#8a5508"))
    b.append(T(tx + 140, ty + 50, "transceiver module", 13, 400, "middle", "#8a5508"))
    b.append(T(tx + 140, ty + 68, "(MAX3485 / SP3485 class)", 11, 400, "middle", MUTED))
    left = [("VCC", 385), ("DI", 420), ("RO", 470), ("DE+RE", 520), ("GND", 570)]
    for name, y in left:
        b.append(T(tx + 12, y + 5, name, 12, 700, family=MONO))
    b.append(T(tx + 228, 825 - 400 + 5, "", 12))
    b.append(T(tx + 228, 470 + 5, "A", 13, 700, "end", family=MONO))
    b.append(T(tx + 228, 520 + 5, "B", 13, 700, "end", family=MONO))
    # wires pin -> transceiver
    b.append(P(f"M320,370 L470,370 L470,385 L{tx},385", "#a05a00", 2))
    b.append(L(320, 420, tx, 420, AMBER, 2))
    b.append(L(320, 470, tx, 470, AMBER, 2))
    b.append(L(320, 520, tx, 520, AMBER, 2))
    b.append(P(f"M{tx},570 L500,570 L500,300", INK, 2))
    b.append(f'<circle cx="500" cy="300" r="4" fill="{INK}"/>')
    b.append(T(340, 412, "TX → DI", 11, 600, fill=MUTED))
    b.append(T(340, 462, "RX ← RO", 11, 600, fill=MUTED))
    b.append(T(340, 512, "high = transmit", 11, 600, fill=MUTED))
    # A/B to rails
    b.append(P(f"M{tx + 240},470 L900,470 L900,820 L980,820", AMBER, 2.5))
    b.append(P(f"M{tx + 240},520 L870,520 L870,860 L980,860", AMBER, 2.5))
    b.append(f'<circle cx="980" cy="820" r="5" fill="{AMBER}"/><circle cx="980" cy="860" r="5" fill="{AMBER}"/>')
    # termination
    b.append(R(1227, 826, 26, 28, "#fff", INK, 1.5, 3))
    b.append(L(1240, 820, 1240, 826, INK, 1.5) + L(1240, 854, 1240, 860, INK, 1.5))
    b.append(T(1290, 900, "120 Ω terminator at BOTH ends of the bus", 12, 600, "end", MUTED))
    # slot ID straps
    b.append(R(400, 645, 400, 115, TEAL_L, TEAL, 1.5, 10))
    b.append(T(420, 746, "Slot ID straps - example: slot 5 = 0101", 13, 700, fill=TEAL))
    bits = [("bit0", True), ("bit1", False), ("bit2", True), ("bit3", False)]
    for i, (n, gnd) in enumerate(bits):
        x = 450 + i * 90
        b.append(L(x, 630, x, 690, TEAL, 2))
        b.append(T(x, 720, n, 11, 700, "middle", TEAL))
        if gnd:
            b.append(P(f"M{x - 12},696 h24 M{x - 8},702 h16 M{x - 4},708 h8", INK, 2))
            b.append(T(x + 26, 700, "GND", 10, 700, fill=INK))
        else:
            b.append(T(x + 8, 700, "open", 10, 400, fill=MUTED))
    b.append(P("M320,590 L380,590 L380,630 L720,630", TEAL, 4))
    b.append(T(390, 624, "4 separate wires", 11, 600, fill=TEAL))
    b.append(T(730, 594, "", 11))
    b.append(T(400, 780, "Grounded = 1 (Pi uses internal pull-ups). Solder jumpers or a 4-way DIP switch per slot.", 11, 400, fill=MUTED))
    # LED
    b.append(L(320, 680, 360, 680, GREEN, 2))
    b.append(P("M360,680 L360,840 L380,840", GREEN, 2))
    b.append(R(380, 830, 60, 20, "#fff", INK, 1.5, 3))
    b.append(T(410, 866, "330 Ω", 11, 600, "middle", MUTED))
    b.append(L(440, 840, 470, 840, GREEN, 2))
    b.append(P("M470,828 L470,852 L492,840 Z", GREEN, 1.5, GREEN))
    b.append(L(492, 828, 492, 852, GREEN, 2))
    b.append(L(492, 840, 520, 840, INK, 2))
    b.append(P("M520,830 v20 M526,834 v12 M532,838 v4", INK, 2))
    b.append(T(470, 890, "front-panel slot LED", 12, 600, "middle", GREEN))
    # notes
    b.append(R(980, 360, 420, 400, "#fff", LINE, 1.2, 10))
    b.append(T(1000, 390, "Build notes", 16, 700))
    notes = ["Use thick wire for 5 V/GND rails (≥ 1.5 mm² /", "16 AWG) and feed each 4-slot group separately.",
             "", "Set the bucks to 5.1 V measured AT the header,", "under load. Below ~4.9 V the Pi throttles -", "`casectl status` shows POWER WARN.",
             "", "Never hot-plug a powered header: switch the", "slot OFF, insert the Pi, then switch it ON.",
             "", "Leave pins 27/28 (HAT EEPROM) unconnected.", "", "Connect EVERY GND pin - it lowers noise and", "spreads the current."]
    for i, s in enumerate(notes):
        b.append(T(1000, 420 + i * 22, s, 13, 400, fill=MUTED if s else INK))
    return svg(W, H, "".join(b), "PiCase backplane wiring")


# ---------------------------------------------------------------------------
# 5. GPIO header pinout
# ---------------------------------------------------------------------------
def pinout():
    W, H = 1100, 1060
    names = {1: "3V3", 2: "5V", 3: "GPIO2", 4: "5V", 5: "GPIO3", 6: "GND", 7: "GPIO4", 8: "GPIO14 TXD",
             9: "GND", 10: "GPIO15 RXD", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
             16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25",
             23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
             30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16",
             37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21"}
    use = {2: ("5 V power in", RED), 4: ("5 V power in", RED), 1: ("RS-485 VCC", "#a05a00"),
           8: ("RS-485 DI", AMBER), 10: ("RS-485 RO", AMBER), 11: ("RS-485 DE/RE", AMBER),
           29: ("slot ID bit0", TEAL), 31: ("slot ID bit1", TEAL), 33: ("slot ID bit2", TEAL),
           35: ("slot ID bit3", TEAL), 37: ("slot LED", GREEN), 27: ("leave open", RED), 28: ("leave open", RED)}
    for g in (6, 9, 14, 20, 25, 30, 34, 39):
        use[g] = ("GND (all tied)", INK)
    b = [heading(W, "GPIO header - what the backplane uses", "Raspberry Pi 3 / 4 / 5 40-pin header, viewed from the top with the USB/Ethernet end pointing down.")]
    hx, hy = 470, 140
    b.append(R(hx - 6, hy - 16, 132, 20 * 42 + 22, "#1b232c", INK, 2, 10))
    for i in range(20):
        for c in range(2):
            pin = i * 2 + c + 1
            x = hx + 20 + c * 80
            y = hy + 12 + i * 42
            u = use.get(pin)
            col = u[1] if u else "#56636f"
            fill = col if u and pin not in (27, 28) else ("#1b232c" if pin in (27, 28) else "#3a4552")
            b.append(f'<rect x="{x - 14}" y="{y - 14}" width="28" height="28" rx="{2 if pin == 1 else 14}" '
                     f'fill="{"#000" if col == INK else fill}" stroke="{"#e9edf1" if col == INK else (col if u else "#77828e")}" stroke-width="2.5"/>')
            b.append(T(x, y + 4, str(pin), 11, 700, "middle", "#fff"))
            name = names[pin]
            if c == 0:
                b.append(T(x - 34, y + 5, name, 13, 600 if u else 400, "end", INK if u else "#98a2ad", MONO))
                if u:
                    b.append(T(x - 160, y + 5, u[0], 12, 700, "end", u[1]))
            else:
                b.append(T(x + 34, y + 5, name, 13, 600 if u else 400, "start", INK if u else "#98a2ad", MONO))
                if u:
                    b.append(T(x + 146, y + 5, u[0], 12, 700, "start", u[1]))
    b.append(T(W / 2, H - 50, "Everything not coloured stays free for your own projects (I²C on 3/5, SPI on 19/21/23, PWM on 12/32/33...).", 13, 400, "middle", MUTED))
    b.append(T(W / 2, H - 28, "Only RS-485, slot ID and LED pins are wired on the backplane - the free pins are NOT connected between slots.", 13, 400, "middle", MUTED))
    return svg(W, H, "".join(b), "PiCase GPIO usage")


# ---------------------------------------------------------------------------
# 6. Adding a node
# ---------------------------------------------------------------------------
def add_node():
    W, H = 1400, 620
    b = [heading(W, "Adding a Raspberry Pi to the case", "The rest of the cluster keeps running - only the slot you are filling is switched off.")]
    steps = [
        ("1", "Prepare the card", ["Flash Raspberry Pi OS Lite", "Run setup_worker.sh once", "(same card works in any slot)"]),
        ("2", "Slot switch OFF", ["Lift the hinged deck", "Flip the red switch for an", "empty slot to OFF"]),
        ("3", "Slide the Pi in", ["Board into the card guide,", "header onto the right-angle", "socket. Plug the patch lead."]),
        ("4", "Slot switch ON", ["Slot LED lights in ~30 s.", "Dashboard: 'slot 05 joined'", "Then: casectl adopt 5"]),
    ]
    for i, (n, title, lines) in enumerate(steps):
        x = 40 + i * 340
        b.append(R(x, 120, 320, 450, PANEL, LINE, 1.2, 14))
        b.append(badge(x + 30, 150, n))
        b.append(T(x + 52, 156, title, 18, 700))
        for j, s in enumerate(lines):
            b.append(T(x + 24, 470 + j * 24, s, 14, 400, fill=MUTED))
        cx, cy = x + 160, 300
        if i == 0:   # SD card + laptop
            b.append(R(cx - 110, cy - 80, 150, 100, "#dfe4ea", INK, 2, 8))
            b.append(R(cx - 100, cy - 70, 130, 80, "#0f1a22", "none", 0, 4))
            b.append(T(cx - 35, cy - 40, "$ sudo ./setup_", 10, 400, "middle", "#7ee08f", MONO))
            b.append(T(cx - 35, cy - 24, "  worker.sh", 10, 400, "middle", "#7ee08f", MONO))
            b.append(R(cx - 130, cy + 20, 190, 12, "#c3cbd3", INK, 1.5, 4))
            b.append(P(f"M{cx + 60},{cy - 10} h50 l14,14 v56 h-64 z", INK, 2, "#2f64d6"))
            b.append(R(cx + 70, cy + 32, 44, 22, "#fff", "none", 0, 2))
            b.append(T(cx + 92, cy + 47, "SD", 12, 700, "middle", BLUE))
        if i in (1, 3):  # slot switch
            on = i == 3
            b.append(R(cx - 110, cy - 60, 220, 130, PCB_L, PCB, 2, 8))
            b.append(R(cx - 40, cy - 30, 80, 60, "#2a2a2a", INK, 2, 6))
            b.append(R(cx - 32 + (36 if on else 0), cy - 22, 36, 44, RED, INK, 1.5, 4))
            b.append(T(cx - 70, cy + 6, "OFF", 13, 700, "middle", INK if not on else MUTED))
            b.append(T(cx + 72, cy + 6, "ON", 13, 700, "middle", INK if on else MUTED))
            b.append(f'<circle cx="{cx}" cy="{cy + 52}" r="9" fill="{GREEN if on else "#56636f"}" stroke="{INK}"/>')
            if on:
                b.append(f'<circle cx="{cx}" cy="{cy + 52}" r="16" fill="none" stroke="{GREEN}" stroke-width="2" opacity="0.5"/>')
        if i == 2:  # blade sliding into socket (side view)
            b.append(R(cx - 120, cy + 50, 240, 18, PCB_L, PCB, 2, 3))
            b.append(R(cx - 70, cy + 28, 120, 22, "#222", INK, 1.5, 2))
            b.append(T(cx - 10, cy + 43, "2x20 socket", 10, 700, "middle", "#ddd"))
            b.append(R(cx - 80, cy - 100, 140, 112, "#e7ece9", PCB, 2, 4))
            b.append(R(cx - 70, cy - 2, 120, 10, "#333", "none", 0, 1))
            b.append(T(cx - 10, cy - 50, "Pi", 22, 700, "middle", PCB))
            b.append(L(cx + 90, cy - 90, cx + 90, cy - 10, INK, 2, 'marker-end="url(#arr)"'))
            b.append(R(cx + 64, cy - 112, 22, 140, "#9aa5b1", "none", 0, 3))
            b.append(T(cx + 112, cy - 100, "guide", 11, 600, fill=MUTED))
    return svg(W, H, "".join(b), "Adding a node")


DIAGRAMS = {
    "01_briefcase_overview": briefcase,
    "02_internal_layout": layout,
    "03_network_topology": network,
    "04_backplane_wiring": backplane,
    "05_gpio_pinout": pinout,
    "06_adding_a_node": add_node,
}

if __name__ == "__main__":
    try:
        import cairosvg
    except ImportError:
        cairosvg = None
    for name, fn in DIAGRAMS.items():
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w") as fh:
            fh.write(fn())
        if cairosvg:
            cairosvg.svg2png(url=path, write_to=os.path.join(OUT, name + ".png"), scale=1.5)
        print("wrote", name)
