"""Reference: stream.frame_codec."""
from __future__ import annotations


# LC 271 Encode and Decode Strings
class FrameCodec:
    def encode(self, chunks: list[str]) -> str:
        return "".join(f"{len(s)}#{s}" for s in chunks)

    def decode(self, data: str) -> list[str]:
        out: list[str] = []
        i = 0
        while i < len(data):
            j = data.index("#", i)
            n = int(data[i:j])
            out.append(data[j + 1 : j + 1 + n])
            i = j + 1 + n
        return out
