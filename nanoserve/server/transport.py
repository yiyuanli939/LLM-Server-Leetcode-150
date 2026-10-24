"""Framework: the streaming wire protocol between the server and its clients (M2).

The server's multiplexed event stream ``(tick, rid, chunk)`` goes over a byte channel:

    server events ──Transport──▶ per tick: FrameCodec message ──utf-8──▶ fixed-size packets ──▶ wire
    wire ──StreamClient──▶ byte buffer ──(valid UTF-8?)──▶ live preview ; complete message ──▶ frames

  * Framing: each tick's events become one message, ``FrameCodec.encode([rid, chunk, rid, chunk, …])``.
    Chunks are model output and may contain anything (digits, '#', newlines, CJK, emoji), so the codec
    must be length-prefixed, never delimiter-based (stream.frame_codec).
  * Packets: the message's UTF-8 bytes are cut every ``packet_size`` bytes, *ignoring* character
    boundaries — exactly like a socket. Each packet carries (message id, offset, total length, payload).
  * Client: appends payload bytes to the message's buffer. It shows a live preview only when the buffer
    is valid UTF-8 as a whole (server.utf8_ok) — so it never decodes half of a multi-byte character —
    and decodes the frames once the message is complete.

Exercises this file calls (M2): stream.frame_codec, server.utf8_ok.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence

from nanoserve.server.utf8 import utf8_valid
from nanoserve.stream.protocol import FrameCodec


@dataclass(frozen=True)
class Packet:
    msg: int          # message id (one message per tick)
    tick: int
    offset: int       # byte offset of the payload within the message
    total: int        # message length in bytes
    payload: bytes


class Transport:
    """Server side: frame each tick's events and cut the bytes into packets."""

    def __init__(self, packet_size: int = 64) -> None:
        if packet_size < 1:
            raise ValueError("packet_size must be >= 1")
        self.packet_size = packet_size
        self.codec = FrameCodec()
        self._next_msg = 0

    def message(self, events: Sequence[tuple[str, str]]) -> str:
        """One tick's events [(rid, chunk), …] as a single framed string."""
        flat: list[str] = []
        for rid, chunk in events:
            flat += [rid, chunk]
        return self.codec.encode(flat)

    def packets(self, tick: int, events: Sequence[tuple[str, str]]) -> list[Packet]:
        data = self.message(events).encode("utf-8")
        msg, self._next_msg = self._next_msg, self._next_msg + 1
        n = self.packet_size
        if not data:  # a codec may encode "nothing" as ""; still send one (empty) packet so it arrives
            return [Packet(msg, tick, 0, 0, b"")]
        return [Packet(msg, tick, off, len(data), data[off:off + n]) for off in range(0, len(data), n)]

    def stream(self, events: Iterable[tuple[int, str, str]]) -> Iterator[Packet]:
        """Packetize a server's multiplexed event stream (``ServerReport.events``), one message per tick."""
        batch: list[tuple[str, str]] = []
        tick: int | None = None
        for t, rid, chunk in events:
            if tick is not None and t != tick:
                yield from self.packets(tick, batch)
                batch = []
            tick = t
            batch.append((rid, chunk))
        if tick is not None:
            yield from self.packets(tick, batch)

    def chunk_stream(self, chunks: Sequence[str], rid: str = "r", tick: int = 0) -> list[Packet]:
        """One request's chunks as a single message (handy for sending a whole response)."""
        return self.packets(tick, [(rid, c) for c in chunks])


@dataclass
class _Inbox:
    tick: int
    total: int
    buf: bytearray = field(default_factory=bytearray)


class StreamClient:
    """Client side: reassemble packets, preview valid prefixes, decode complete messages."""

    def __init__(self) -> None:
        self.codec = FrameCodec()
        self._inbox: dict[int, _Inbox] = {}
        self.text: dict[str, str] = {}            # rid -> everything received so far
        self.frames: list[tuple[int, str, str]] = []  # decoded (tick, rid, chunk), in order
        self.previews: list[str] = []              # live previews shown (decoded partial messages)
        self.held: int = 0                         # times a packet ended inside a multi-byte character

    def receive(self, pkt: Packet) -> str | None:
        """Feed one packet. Returns the preview text if the buffer can be shown right now."""
        box = self._inbox.setdefault(pkt.msg, _Inbox(pkt.tick, pkt.total))
        if pkt.offset != len(box.buf):
            raise ValueError(f"packet {pkt.msg}@{pkt.offset} out of order (have {len(box.buf)} bytes)")
        box.buf += pkt.payload
        preview = None
        if box.buf:
            if utf8_valid(list(box.buf)):
                preview = box.buf.decode("utf-8")  # safe: only whole characters
                self.previews.append(preview)
            else:
                self.held += 1
        if len(box.buf) == box.total:
            self._complete(pkt.msg)
        return preview

    def _complete(self, msg: int) -> None:
        box = self._inbox.pop(msg)
        flat = self.codec.decode(box.buf.decode("utf-8"))
        for rid, chunk in zip(flat[0::2], flat[1::2]):
            self.frames.append((box.tick, rid, chunk))
            self.text[rid] = self.text.get(rid, "") + chunk

    def receive_all(self, packets: Iterable[Packet]) -> "StreamClient":
        for p in packets:
            self.receive(p)
        return self

    @property
    def pending(self) -> int:
        """Messages started but not complete yet."""
        return len(self._inbox)


def roundtrip(events: Sequence[tuple[int, str, str]], packet_size: int = 64) -> StreamClient:
    """Send a server's events through the wire and return the client that received them."""
    return StreamClient().receive_all(Transport(packet_size).stream(events))
