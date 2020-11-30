import math
from typing import List, Dict

from . import Frame
from .packet import Packet


class FrameBuilder:
    def __init__(self, n_expected_packets: int, priority: Frame.priority):
        self.n_expected_packets = n_expected_packets
        self.size = 0
        self.priority = priority
        self.data_arr: List[bytes] = [None] * n_expected_packets

    def emplace(self, seq_no: int, data: bytes) -> bool:
        """
        :param seq_no: packet number in frame
        :param data: data contained in packet
        :return: true if data replaces None, false if position has already been filled
        """
        if seq_no >= self.n_expected_packets:
            raise Exception(
                "Packet # is greater than what was initially expected\nExpected Packets: {}\nPacket #: {}".format(
                    self.n_expected_packets, seq_no
                )
            )
        if self.data_arr[seq_no] is None:
            self.data_arr[seq_no] = data
            self.size += 1
            return True
        return False

    def is_complete(self) -> bool:
        """
        :return: true if frame is filled, false otherwise
        """
        return self.size == self.n_expected_packets

    def get_data_as_bytes(self) -> bytes:
        return b"".join(x for x in self.data_arr)

    def to_frame(self):
        return Frame(data=self.get_data_as_bytes())

    def to_dict(self) -> Dict:
        """
        :return: dictionary of Frame
        """
        return {
            "n_expected_packets": self.n_expected_packets,
            "size": self.size,
            "data": "".join(x for x in self.data_arr),
        }
