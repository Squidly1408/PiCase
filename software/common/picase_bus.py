"""
picase_bus.py - shared code for the PiCase management bus.

The management bus is a half-duplex RS-485 line that runs along the
backplane. Every Raspberry Pi plugs into the backplane through its
40-pin GPIO header and talks on the bus using its hardware UART
(GPIO14 TXD / GPIO15 RXD) through a small 3.3 V RS-485 transceiver.
A third GPIO (GPIO17) switches the transceiver between send and receive.

Only the controller (slot 0) ever starts a conversation. Workers only
reply when they are addressed, so there are never two talkers at once.

Frame layout (all multi-byte fields big-endian):

    +------+--------+-----+-----+------+-----+-----------+--------+
    | SOF  | LEN(2) | DST | SRC | TYPE | SEQ | PAYLOAD.. | CRC(2) |
    +------+--------+-----+-----+------+-----+-----------+--------+
      0x7E   bytes    1     1     1      1     LEN bytes   CRC-16/CCITT
                                                           over LEN..PAYLOAD

Payloads are compact UTF-8 JSON objects (or empty).
"""

from __future__ import annotations

import json
import queue
import struct
import threading
import time
from dataclasses import dataclass, field

PROTOCOL_VERSION = 1

SOF = 0x7E
MAX_PAYLOAD = 1024
HEADER_LEN = 1 + 2 + 4          # SOF + LEN + DST SRC TYPE SEQ
CRC_LEN = 2

ADDR_CONTROLLER = 0x00
ADDR_BROADCAST = 0xFF
MAX_SLOTS = 16                  # 4 slot-ID pins -> slots 0..15 (0 = controller)

# Message types. Replies have the high bit set.
PING = 0x01        # controller -> worker: "are you there?"
PONG = 0x81        # worker -> controller: identity (hostname, ip, mac, model...)
STATS_REQ = 0x02   # controller -> worker: request health stats
STATS = 0x82       # worker -> controller: temps, load, memory, throttling
IDENTIFY = 0x03    # controller -> worker: blink the slot LED
REBOOT = 0x04      # controller -> worker: reboot now
SHUTDOWN = 0x05    # controller -> worker: power off safely
ACK = 0x8F
NAK = 0x90

TYPE_NAMES = {
    PING: "PING", PONG: "PONG", STATS_REQ: "STATS_REQ", STATS: "STATS",
    IDENTIFY: "IDENTIFY", REBOOT: "REBOOT", SHUTDOWN: "SHUTDOWN",
    ACK: "ACK", NAK: "NAK",
}

# GPIO assignments (BCM numbering) - must match hardware/backplane_pinout.md
GPIO_UART_TX = 14     # header pin 8
GPIO_UART_RX = 15     # header pin 10
GPIO_RS485_DE = 17    # header pin 11  (high = transmit)
GPIO_SLOT_ID = (5, 6, 13, 19)   # header pins 29, 31, 33, 35 (bit0..bit3, active low)
GPIO_SLOT_LED = 26    # header pin 37  (front-panel slot LED)


# --------------------------------------------------------------------------
# Framing
# --------------------------------------------------------------------------

def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class Frame:
    dst: int
    src: int
    type: int
    seq: int = 0
    payload: bytes = b""

    @property
    def data(self) -> dict:
        if not self.payload:
            return {}
        try:
            return json.loads(self.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def __repr__(self) -> str:
        name = TYPE_NAMES.get(self.type, hex(self.type))
        return f"<Frame {name} {self.src}->{self.dst} seq={self.seq} {self.payload[:60]!r}>"


def encode(frame: Frame) -> bytes:
    if len(frame.payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    body = struct.pack(">HBBBB", len(frame.payload), frame.dst & 0xFF,
                       frame.src & 0xFF, frame.type & 0xFF, frame.seq & 0xFF)
    body += frame.payload
    return bytes([SOF]) + body + struct.pack(">H", crc16_ccitt(body))


def make(dst: int, src: int, mtype: int, seq: int = 0, data: dict | None = None) -> bytes:
    payload = b""
    if data:
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return encode(Frame(dst, src, mtype, seq, payload))


class Decoder:
    """Incremental decoder. Feed it raw bytes; it yields complete frames and
    silently resynchronises after line noise or a corrupt frame."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.bad_frames = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buf.extend(data)
        frames: list[Frame] = []
        while True:
            start = self.buf.find(bytes([SOF]))
            if start < 0:
                self.buf.clear()
                break
            if start:
                del self.buf[:start]
            if len(self.buf) < HEADER_LEN:
                break
            length = struct.unpack_from(">H", self.buf, 1)[0]
            if length > MAX_PAYLOAD:
                self.bad_frames += 1
                del self.buf[0]          # not a real SOF; skip it
                continue
            total = HEADER_LEN + length + CRC_LEN
            if len(self.buf) < total:
                break
            body = bytes(self.buf[1:HEADER_LEN + length])
            (crc,) = struct.unpack_from(">H", self.buf, HEADER_LEN + length)
            if crc != crc16_ccitt(body):
                self.bad_frames += 1
                del self.buf[0]
                continue
            _, dst, src, mtype, seq = struct.unpack_from(">HBBBB", body, 0)
            frames.append(Frame(dst, src, mtype, seq, body[6:]))
            del self.buf[:total]
        return frames


# --------------------------------------------------------------------------
# Transports
# --------------------------------------------------------------------------

class Bus:
    """Base class: send raw bytes, receive decoded frames."""

    def __init__(self) -> None:
        self.decoder = Decoder()

    def send(self, raw: bytes) -> None:
        raise NotImplementedError

    def _read_raw(self, timeout: float) -> bytes:
        raise NotImplementedError

    def receive(self, timeout: float) -> list[Frame]:
        """Wait up to `timeout` seconds; return whatever complete frames arrived."""
        deadline = time.monotonic() + timeout
        frames: list[Frame] = []
        while not frames:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            frames = self.decoder.feed(self._read_raw(remaining))
        return frames

    def close(self) -> None:
        pass


class SerialBus(Bus):
    """Real hardware: UART + RS-485 transceiver with a GPIO direction pin."""

    def __init__(self, port: str = "/dev/serial0", baud: int = 115200,
                 de_gpio: int | None = GPIO_RS485_DE) -> None:
        super().__init__()
        import serial  # pyserial (apt: python3-serial)
        self.serial = serial.Serial(port, baudrate=baud, timeout=0.01)
        self.char_time = 10.0 / baud
        self.de = None
        if de_gpio is not None:
            from gpiozero import OutputDevice
            self.de = OutputDevice(de_gpio, active_high=True, initial_value=False)

    def send(self, raw: bytes) -> None:
        if self.de:
            self.de.on()
        try:
            self.serial.write(raw)
            self.serial.flush()                 # tcdrain(): wait for FIFO to empty
            time.sleep(self.char_time * 2)      # let the final stop bit leave the wire
        finally:
            if self.de:
                self.de.off()

    def _read_raw(self, timeout: float) -> bytes:
        self.serial.timeout = min(timeout, 0.02)
        waiting = self.serial.in_waiting
        return self.serial.read(waiting or 1)

    def close(self) -> None:
        self.serial.close()
        if self.de:
            self.de.close()


class SimHub:
    """In-memory stand-in for the RS-485 wire, used by tools/simulate.py and
    tests. Everything one endpoint sends is delivered to every other one,
    exactly like a shared bus."""

    def __init__(self) -> None:
        self.endpoints: list["SimBus"] = []
        self.lock = threading.Lock()

    def endpoint(self) -> "SimBus":
        ep = SimBus(self)
        with self.lock:
            self.endpoints.append(ep)
        return ep

    def deliver(self, sender: "SimBus", raw: bytes) -> None:
        with self.lock:
            targets = [e for e in self.endpoints if e is not sender and not e.unplugged]
        for ep in targets:
            ep.inbox.put(raw)


class SimBus(Bus):
    def __init__(self, hub: SimHub) -> None:
        super().__init__()
        self.hub = hub
        self.inbox: "queue.Queue[bytes]" = queue.Queue()
        self.unplugged = False

    def send(self, raw: bytes) -> None:
        if not self.unplugged:
            self.hub.deliver(self, raw)

    def _read_raw(self, timeout: float) -> bytes:
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return b""


# --------------------------------------------------------------------------
# Slot ID
# --------------------------------------------------------------------------

def read_slot_id(pins=GPIO_SLOT_ID) -> int:
    """Read the 4 slot-ID straps from the backplane.

    Each slot connector ties some of the four ID pins to GND. The Pi enables
    its internal pull-ups, so a grounded pin reads 0 and means bit = 1.
    A Pi that is not on the backplane reads slot 0 (controller)."""
    from gpiozero import DigitalInputDevice
    slot = 0
    for bit, pin in enumerate(pins):
        dev = DigitalInputDevice(pin, pull_up=True)
        try:
            if not dev.value:        # value is True when pin is high
                slot |= 1 << bit
        finally:
            dev.close()
    return slot


@dataclass
class NodeState:
    slot: int
    online: bool = False
    missed: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    info: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "slot": self.slot, "online": self.online, "missed": self.missed,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
            "info": self.info, "stats": self.stats,
        }
