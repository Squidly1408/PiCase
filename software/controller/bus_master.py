#!/usr/bin/env python3
"""
bus_master.py - runs on the CONTROLLER Pi (slot 0).

* Polls every backplane slot over the RS-485 management bus.
* Discovers newly inserted Pis automatically (hot-add) and notices removals.
* Keeps /etc/hosts up to date so `ssh picase-node03` just works.
* Exposes a small JSON-lines control socket used by `casectl` and the
  on-screen console.

Usage:
    sudo python3 bus_master.py                       # real hardware
    sudo python3 bus_master.py --port /dev/ttyAMA0   # explicit UART
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, "/opt/picase/common")

import picase_bus as pb  # noqa: E402

log = logging.getLogger("picase.master")

SOCKET_PATH = "/run/picase/master.sock"
STATE_PATH = "/run/picase/nodes.json"
HOSTS_PATH = "/etc/hosts"
HOSTS_BEGIN = "# >>> picase nodes (managed by bus_master) >>>"
HOSTS_END = "# <<< picase nodes <<<"


class Master:
    def __init__(self, bus: pb.Bus, slots=range(1, pb.MAX_SLOTS),
                 reply_timeout: float = 0.08, offline_after: int = 3,
                 stats_every: float = 2.0, manage_hosts: bool = True,
                 state_path: str | None = STATE_PATH) -> None:
        self.bus = bus
        self.slots = list(slots)
        self.reply_timeout = reply_timeout
        self.offline_after = offline_after
        self.stats_every = stats_every
        self.manage_hosts = manage_hosts
        self.state_path = state_path
        self.nodes = {s: pb.NodeState(slot=s) for s in self.slots}
        self.seq = 0
        self.commands: "queue.Queue[tuple[dict, queue.Queue]]" = queue.Queue()
        self.lock = threading.Lock()
        self.events: list[str] = []
        self._stop = threading.Event()
        self._last_stats = {s: 0.0 for s in self.slots}
        self._hosts_snapshot: dict[int, str] = {}

    # -- low level ---------------------------------------------------------
    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def request(self, slot: int, mtype: int, data: dict | None = None,
                timeout: float | None = None) -> pb.Frame | None:
        """Send one request and wait for the matching reply (or None)."""
        seq = self._next_seq()
        self.bus.send(pb.make(slot, pb.ADDR_CONTROLLER, mtype, seq, data))
        deadline = time.monotonic() + (timeout or self.reply_timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            for frame in self.bus.receive(remaining):
                if (frame.dst == pb.ADDR_CONTROLLER and frame.src == slot
                        and frame.seq == seq):
                    return frame

    def broadcast(self, mtype: int, data: dict | None = None) -> None:
        self.bus.send(pb.make(pb.ADDR_BROADCAST, pb.ADDR_CONTROLLER, mtype,
                              self._next_seq(), data))

    def _event(self, msg: str) -> None:
        log.info(msg)
        with self.lock:
            self.events.append(time.strftime("%H:%M:%S ") + msg)
            del self.events[:-50]

    # -- polling -----------------------------------------------------------
    def poll_slot(self, slot: int) -> None:
        node = self.nodes[slot]
        now = time.monotonic()
        if not node.online:
            reply = self.request(slot, pb.PING)
            if reply and reply.type == pb.PONG:
                with self.lock:
                    node.online, node.missed = True, 0
                    node.info = reply.data
                    node.first_seen = node.last_seen = time.time()
                self._event(f"slot {slot:02d} joined: {node.info.get('h', '?')} "
                            f"{node.info.get('ip', 'no-ip')}")
                self._last_stats[slot] = 0.0
            return

        if now - self._last_stats[slot] < self.stats_every:
            return
        self._last_stats[slot] = now
        reply = self.request(slot, pb.STATS_REQ)
        with self.lock:
            if reply and reply.type == pb.STATS:
                node.missed = 0
                node.last_seen = time.time()
                node.stats = reply.data
                # IP can change (DHCP renew, cable moved) - stats carry it too
                if reply.data.get("ip") and reply.data["ip"] != node.info.get("ip"):
                    node.info["ip"] = reply.data["ip"]
                return
            node.missed += 1
            went_offline = node.missed >= self.offline_after
            if went_offline:
                node.online = False
                node.stats = {}
        if went_offline:
            self._event(f"slot {slot:02d} left the bus ({node.info.get('h', '?')})")

    def handle_command(self, req: dict) -> dict:
        cmd = req.get("cmd")
        if cmd == "status":
            with self.lock:
                return {"ok": True, "nodes": [n.as_dict() for n in self.nodes.values()],
                        "events": list(self.events[-15:]),
                        "bad_frames": self.bus.decoder.bad_frames}
        if cmd in ("identify", "reboot", "shutdown"):
            mtype = {"identify": pb.IDENTIFY, "reboot": pb.REBOOT,
                     "shutdown": pb.SHUTDOWN}[cmd]
            target = req.get("slot")
            if target == "all":
                targets = [s for s, n in self.nodes.items() if n.online]
            else:
                try:
                    targets = [int(target)]
                except (TypeError, ValueError):
                    return {"ok": False, "error": "slot must be a number or 'all'"}
            results = {}
            for slot in targets:
                if slot not in self.nodes:
                    results[slot] = "no such slot"
                    continue
                reply = self.request(slot, mtype, {"secs": req.get("secs", 10)},
                                     timeout=0.3)
                results[slot] = "ok" if reply and reply.type == pb.ACK else "no reply"
                if reply and cmd in ("reboot", "shutdown"):
                    self._event(f"slot {slot:02d} {cmd} requested")
            return {"ok": True, "results": results}
        return {"ok": False, "error": f"unknown command {cmd!r}"}

    def step(self) -> None:
        """One pass over all slots, servicing queued commands in between."""
        for slot in self.slots:
            self._drain_commands()
            self.poll_slot(slot)
        self._after_pass()

    def _drain_commands(self) -> None:
        while True:
            try:
                req, reply_q = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                reply_q.put(self.handle_command(req))
            except Exception as exc:  # never let a bad command kill the bus
                log.exception("command failed")
                reply_q.put({"ok": False, "error": str(exc)})

    def submit(self, req: dict, timeout: float = 10.0) -> dict:
        """Thread-safe: queue a command for the polling loop and wait."""
        reply_q: "queue.Queue[dict]" = queue.Queue()
        self.commands.put((req, reply_q))
        try:
            return reply_q.get(timeout=timeout)
        except queue.Empty:
            return {"ok": False, "error": "timeout waiting for bus"}

    def _after_pass(self) -> None:
        if self.state_path:
            try:
                os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
                tmp = self.state_path + ".tmp"
                with open(tmp, "w") as fh:
                    json.dump(self.handle_command({"cmd": "status"}), fh)
                os.replace(tmp, self.state_path)
            except OSError:
                pass
        if self.manage_hosts:
            self._update_hosts()

    def _update_hosts(self) -> None:
        wanted = {}
        with self.lock:
            for slot, node in self.nodes.items():
                if node.online and node.info.get("ip"):
                    wanted[slot] = node.info["ip"]
        if wanted == self._hosts_snapshot:
            return
        try:
            with open(HOSTS_PATH) as fh:
                lines = fh.read().splitlines()
            out, skipping = [], False
            for line in lines:
                if line.strip() == HOSTS_BEGIN:
                    skipping = True
                elif line.strip() == HOSTS_END:
                    skipping = False
                elif not skipping:
                    out.append(line)
            out.append(HOSTS_BEGIN)
            for slot, ip in sorted(wanted.items()):
                out.append(f"{ip}\tpicase-node{slot:02d}")
            out.append(HOSTS_END)
            with open(HOSTS_PATH + ".picase.tmp", "w") as fh:
                fh.write("\n".join(out) + "\n")
            os.replace(HOSTS_PATH + ".picase.tmp", HOSTS_PATH)
            self._hosts_snapshot = wanted
        except OSError as exc:
            log.warning("could not update %s: %s", HOSTS_PATH, exc)
            self.manage_hosts = False

    def run(self) -> None:
        self._event("bus master started")
        while not self._stop.is_set():
            self.step()
            time.sleep(0.05)

    def stop(self) -> None:
        self._stop.set()


def serve_socket(master: Master, path: str = SOCKET_PATH, group: str = "picase") -> None:
    """JSON-lines control socket: one request per line, one reply per line."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.unlink(path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    try:
        import grp
        os.chown(path, 0, grp.getgrnam(group).gr_gid)
        os.chmod(path, 0o660)
    except (KeyError, PermissionError, ImportError):
        os.chmod(path, 0o666)
    srv.listen(8)

    def client(conn: socket.socket) -> None:
        with conn, conn.makefile("rwb") as fh:
            for line in fh:
                try:
                    req = json.loads(line)
                except ValueError:
                    resp = {"ok": False, "error": "bad json"}
                else:
                    resp = master.submit(req)
                fh.write((json.dumps(resp) + "\n").encode())
                fh.flush()

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=client, args=(conn,), daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser(description="PiCase management-bus master")
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--slots", type=int, default=pb.MAX_SLOTS - 1,
                    help="number of worker slots on your backplane (default 15)")
    ap.add_argument("--socket", default=SOCKET_PATH)
    ap.add_argument("--no-hosts", action="store_true", help="don't edit /etc/hosts")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    bus = pb.SerialBus(args.port, args.baud)
    master = Master(bus, slots=range(1, args.slots + 1), manage_hosts=not args.no_hosts)
    threading.Thread(target=serve_socket, args=(master, args.socket), daemon=True).start()
    try:
        master.run()
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()


if __name__ == "__main__":
    main()
