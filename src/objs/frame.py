import math
import struct
from enum import Enum
from functools import total_ordering
from typing import List, Dict

BYTE_LOC = 4


class Frame:
    def __init__(self, frame_no: int = 0, data: bytes = b""):
        self.frame_no = frame_no
        self.data = data

    def pack(self):
        return struct.pack(
            f"!I{len(self.data)}s",
            self.frame_no,
            self.data
        )

    @staticmethod
    def unpack(msg):
        t = struct.unpack(f"!I{len(msg) - 4 * 1}s", msg)
        return Frame(t[0], t[1])  # Takes all except for the padding

    class Priority(Enum):
        LOW = 0b000
        NORMAL = 0b001
        IMPORTANT = 0b010
        CRITICAL = 0b011

        def __lt__(self, other):
            if self.__class__ is other.__class__:
                return self.value < other.value
            return NotImplemented

        def __gt__(self, other):
            if self.__class__ is other.__class__:
                return self.value > other.value
            return NotImplemented

        def __ge__(self, other):
            if self.__class__ is other.__class__:
                return self.value >= other.value
            return NotImplemented

        def __le__(self, other):
            if self.__class__ is other.__class__:
                return self.value <= other.value
            return NotImplemented

    def split_into_chunks(self, chunk_size: int) -> str:
        number_of_packets = math.ceil(len(self.data) / chunk_size)
        # packet_data = [None] * number_of_packets
        for i in range(0, number_of_packets):
            if (i + 1) * chunk_size < len(self.data):
                yield self.data[i * chunk_size: (i + 1) * chunk_size]
            else:
                yield self.data[i * chunk_size:]

    @property
    def priority(self) -> Priority:
        priority_byte = self.data[BYTE_LOC] >> 5
        return self.Priority(priority_byte)

    def to_dict(self) -> Dict:
        return {'frame_no': self.frame_no, 'data': self.data}
