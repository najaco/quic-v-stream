import struct
from typing import Dict


class Ack:
    def __init__(self, frame_no: int):
        self.frame_no = frame_no

    def pack(self):
        return struct.pack("!I", self.frame_no)

    @staticmethod
    def unpack(msg):
        t = struct.unpack("!I", msg)
        return Ack(frame_no=t[0])

    def to_dict(self) -> Dict:
        return {
            "frame_no": self.frame_no,
        }
