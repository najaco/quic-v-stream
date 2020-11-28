import struct
from typing import Dict


class Metadata:
    def __init__(self, file_name: str, number_of_frames: int):
        self.file_name = file_name
        self.number_of_frames = number_of_frames

    def pack(self):
        return struct.pack(
            "!I{}s".format(len(self.file_name)),
            self.number_of_frames,
            self.file_name.encode("utf-8"),
        )

    @staticmethod
    def unpack(msg):
        t = struct.unpack("!I{}s".format(len(msg) - 4 * 1), msg)
        return Metadata(number_of_frames=t[0], file_name=t[1].decode("utf-8"))

    def to_dict(self) -> Dict:
        return {"file_name": self.file_name, "number_of_frames": self.number_of_frames}
