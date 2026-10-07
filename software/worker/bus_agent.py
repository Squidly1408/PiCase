#!/usr/bin/env python3
"""
bus_agent.py - runs on every WORKER Pi (slots 1-15).

* Reads its slot number from the ID straps on the backplane connector.
* Optionally renames the Pi to picase-nodeNN to match its slot.
* Answers the controller on the RS-485 management bus with identity,
  health stats, and handles identify / reboot / shutdown commands.

Usage:
    sudo python3 bus_agent.py --set-hostname
    sudo python3 bus_agent.py --slot 3      # override straps (bench testing)
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, "/opt/picase/common")

import picase_bus as pb  # noqa: E402

log = logging.getLogger("picase.agent")
AGENT_VERSION = "0.1.0"


# --------------------------------------------------------------------------
# System information helpers (all fail soft so the agent runs anywhere)
# --------------------------------------------------------------------------

def _read(path: str, default: str = "") -> str:
    try:
        with open(path) as fh:
            return fh.read().strip().strip("\x00")
    except OSError:
        return default


def primary_ip(iface: str = "eth0") -> str:
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show", iface],
                             capture_output=True, text=True, timeout=2).stdout
        for part in out.split():
            if "/" in part and part[0].isdigit():
                return part.split("/")[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def cpu_temp() -> float | None:
    raw = _read("/sys/class/thermal/thermal_zone0/temp")
    return round(int(raw) / 1000, 1) if raw.isdigit() else None


def mem_used_pct() -> float | None:
    info = {}
    for line in _read("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0]) if rest.split() else 0
    if info.get("MemTotal"):
        return round(100 * (1 - info.get("MemAvailable", 0) / info["MemTotal"]), 1)
    return None


def disk_used_pct(path: str = "/") -> float | None:
    try:
        st = os.statvfs(path)
        return round(100 * (1 - st.f_bavail / st.f_blocks), 1)
    except OSError:
        return None


def throttled() -> str:
    """vcgencmd get_throttled -> e.g. '0x0'. Non-zero means under-voltage or
    thermal throttling happened - very useful for diagnosing backplane power."""
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=2).stdout
        return out.strip().split("=")[-1] or "?"
    except (OSError, subprocess.SubprocessError):
        return "n/a"


class CpuMeter:
    def __init__(self) -> None:
        self.prev = self._sample()

    @staticmethod
    def _sample():
        parts = _read("/proc/stat").splitlines()[:1]
        if not parts:
            return None
        nums = [int(x) for x in parts[0].split()[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        return idle, sum(nums)

    def percent(self) -> float | None:
        cur = self._sample()
        if not cur or not self.prev:
            return None
        d_idle, d_total = cur[0] - self.prev[0], cur[1] - self.prev[1]
        self.prev = cur
        return round(100 * (1 - d_idle / d_total), 1) if d_total else 0.0


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

class Agent:
    def __init__(self, bus: pb.Bus, slot: int, iface: str = "eth0",
                 led_gpio: int | None = pb.GPIO_SLOT_LED, dry_run: bool = False,
                 info_override: dict | None = None) -> None:
        if not 1 <= slot < pb.MAX_SLOTS:
            raise ValueError(f"worker slot must be 1-{pb.MAX_SLOTS - 1}, got {slot}")
        self.bus = bus
        self.slot = slot
        self.iface = iface
        self.dry_run = dry_run
        self.cpu = CpuMeter()
        self.info_override = info_override or {}
        self.led = None
        if led_gpio is not None and not dry_run:
            try:
                from gpiozero import LED
                self.led = LED(led_gpio)
                self.led.on()            # solid = agent running
            except Exception as exc:     # no LED fitted / not a Pi
                log.debug("slot LED unavailable: %s", exc)
        self._stop = threading.Event()

    def info(self) -> dict:
        data = {
            "h": socket.gethostname(),
            "ip": primary_ip(self.iface),
            "mac": _read(f"/sys/class/net/{self.iface}/address"),
            "m": _read("/proc/device-tree/model", "unknown")
                 .replace("Raspberry Pi", "RPi").replace(" Model", ""),
            "v": AGENT_VERSION,
            "pv": pb.PROTOCOL_VERSION,
        }
        data.update(self.info_override)
        return data

    def stats(self) -> dict:
        load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
        data = {
            "t": cpu_temp(), "c": self.cpu.percent(),
            "l": round(load, 2) if load is not None else None,
            "mu": mem_used_pct(), "du": disk_used_pct(),
            "thr": throttled(),
            "up": int(float(_read("/proc/uptime", "0").split()[0] or 0)),
            "ip": self.info_override.get("ip") or primary_ip(self.iface),
        }
        return data

    def identify(self, secs: int) -> None:
        def blink():
            if self.led:
                self.led.blink(on_time=0.15, off_time=0.15)
            act = "/sys/class/leds/ACT/trigger"
            if not self.dry_run and os.access(act, os.W_OK):
                with open(act, "w") as fh:
                    fh.write("heartbeat")
            time.sleep(secs)
            if self.led:
                self.led.on()
            if not self.dry_run and os.access(act, os.W_OK):
                with open(act, "w") as fh:
                    fh.write("mmc0")
        threading.Thread(target=blink, daemon=True).start()

    def power(self, action: str) -> None:
        log.warning("controller requested %s", action)
        if self.dry_run:
            return
        # Small delay so our ACK leaves the wire before the UART goes away.
        subprocess.Popen(["sh", "-c", f"sleep 1; systemctl {action}"])

    def reply(self, frame: pb.Frame, mtype: int, data: dict | None = None) -> None:
        self.bus.send(pb.make(pb.ADDR_CONTROLLER, self.slot, mtype, frame.seq, data))

    def handle(self, frame: pb.Frame) -> None:
        if frame.src != pb.ADDR_CONTROLLER:
            return                       # ignore other workers' replies
        broadcast = frame.dst == pb.ADDR_BROADCAST
        if frame.dst != self.slot and not broadcast:
            return
        t = frame.type
        if t == pb.PING and not broadcast:
            self.reply(frame, pb.PONG, self.info())
        elif t == pb.STATS_REQ and not broadcast:
            self.reply(frame, pb.STATS, self.stats())
        elif t == pb.IDENTIFY:
            self.identify(int(frame.data.get("secs", 10)))
            if not broadcast:
                self.reply(frame, pb.ACK)
        elif t in (pb.REBOOT, pb.SHUTDOWN):
            if not broadcast:
                self.reply(frame, pb.ACK)
            self.power("reboot" if t == pb.REBOOT else "poweroff")
        elif not broadcast:
            self.reply(frame, pb.NAK, {"err": "unknown type"})

    def run(self) -> None:
        log.info("agent running in slot %d", self.slot)
        while not self._stop.is_set():
            for frame in self.bus.receive(0.5):
                try:
                    self.handle(frame)
                except Exception:
                    log.exception("error handling %r", frame)

    def stop(self) -> None:
        self._stop.set()


def set_hostname(slot: int) -> None:
    want = f"picase-node{slot:02d}"
    if socket.gethostname() == want:
        return
    log.info("renaming host to %s", want)
    subprocess.run(["hostnamectl", "set-hostname", want], check=False)
    # keep sudo happy: map new name to 127.0.1.1
    try:
        with open("/etc/hosts") as fh:
            lines = [l for l in fh.read().splitlines() if not l.startswith("127.0.1.1")]
        lines.append(f"127.0.1.1\t{want}")
        with open("/etc/hosts", "w") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as exc:
        log.warning("could not update /etc/hosts: %s", exc)


def main() -> None:
    ap = argparse.ArgumentParser(description="PiCase worker bus agent")
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--slot", type=int, help="override slot-ID straps")
    ap.add_argument("--iface", default="eth0")
    ap.add_argument("--set-hostname", action="store_true",
                    help="rename this Pi to picase-nodeNN to match its slot")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    slot = args.slot if args.slot is not None else pb.read_slot_id()
    if slot == 0:
        log.error("slot ID reads 0 (controller slot or not on backplane). "
                  "Seat the Pi in a worker slot or pass --slot N.")
        # Sleep instead of exiting so systemd doesn't spin restarting us.
        while True:
            time.sleep(60)
    if args.set_hostname:
        set_hostname(slot)

    bus = pb.SerialBus(args.port, args.baud)
    agent = Agent(bus, slot, iface=args.iface)
    try:
        agent.run()
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()


if __name__ == "__main__":
    main()
