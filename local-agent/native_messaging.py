import json
import struct
from typing import Any, BinaryIO


def read_message(stream: BinaryIO) -> dict | None:
    raw_length = stream.read(4)
    if len(raw_length) != 4:
        return None

    length = struct.unpack("<I", raw_length)[0]
    if length <= 0:
        return None

    raw_payload = stream.read(length)
    if len(raw_payload) != length:
        return None

    return json.loads(raw_payload.decode("utf-8"))


def write_message(stream: BinaryIO, message: Any) -> None:
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()
