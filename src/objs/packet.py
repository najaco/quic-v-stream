import struct
from typing import Dict

from . import Frame

ID = 1913


class Packet:
    def __init__(
        self,
        frame_no: int,
        seq_no: int,
        total_seq_no: int,
        size: int,
        priority: Frame.priority,
        data: str,
    ):
        self.frame_no: int = frame_no
        self.seq_no: int = seq_no
        self.total_seq_no: int = total_seq_no
        self.size: int = size
        self.priority = priority
        self.data: str = data

    def pack(self):
        return struct.pack(
            "!IIIIII{}s".format(self.size),
            ID,
            self.frame_no,
            self.seq_no,
            self.total_seq_no,
            self.size,
            self.priority.value,
            self.data,
        )

    def to_dict(self) -> Dict:
        return {
            "frame_no": self.frame_no,
            "seq_no": self.seq_no,
            "total_seq_no": self.total_seq_no,
            "size": self.size,
            "data": self.data,
        }

    @staticmethod
    def unpack(msg):
        t = struct.unpack("!IIIIII{}s".format(len(msg) - 4 * 6), msg)
        if t[0] != ID:
            return None
        return Packet(
            t[1], t[2], t[3], t[4], Frame.Priority(t[5]), t[6]
        )  # Takes all except for the padding
