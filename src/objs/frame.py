import math
from enum import Enum
from functools import total_ordering
from typing import List

BYTE_LOC = 4


class Frame:
    def __init__(self, data: bytes, frame_no: int = 0):
        self.data = data
        self.frame_no = frame_no

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

    @property
    def priority(self) -> Priority:
        priority_byte = self.data[BYTE_LOC] >> 5
        return self.Priority(priority_byte)

    def to_data_arr(self, max_data_size: int) -> List[str]:
        number_of_packets = math.ceil(len(self.data) / max_data_size)
        packet_data = [None] * number_of_packets
        for i in range(0, number_of_packets):
            if (i + 1) * max_data_size < len(self.data):
                packet_data[i] = self.data[i * max_data_size : (i + 1) * max_data_size]
            else:
                packet_data[i] = self.data[i * max_data_size :]
        return packet_data
