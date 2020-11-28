import configparser
import logging
import os
from typing import List, Dict

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import ProtocolNegotiated, QuicEvent, StreamDataReceived
from aioquic.tls import SessionTicket

from delta_list.delta_list import DeltaList
from objs.ack import Ack
from objs.frame import Frame
from objs.metadata import Metadata
from objs.packet import Packet

config = configparser.ConfigParser()
config.read("config.ini")
MAX_PKT_SIZE: int = int(config["DEFAULT"]["MaxPacketSize"])
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 6
PRIORITY_THRESHOLD: Frame.Priority = Frame.Priority(
    int(config["DEFAULT"]["PriorityThreshold"])
)
CACHE_PATH: str = config["SERVER"]["CachePath"]
SLEEP_TIME = float(config["SERVER"]["SleepTime"])
RETR_TIME = int(config["SERVER"]["RetransmissionTime"])
RETR_INTERVAL = float(config["SERVER"]["RetransmissionInterval"])

HOST = '127.0.0.1'
PORT = 40205

FILE_DIR = "./assets/"
ENCODING = "ascii"
MAX_DATAGRAM_SIZE = 65536


def cl_ffmpeg(file_path: str, cache_path: str):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )
    cmd = f"ffmpeg -i {file_path} -f image2 -c:v copy -bsf h264_mp4toannexb {cache_path}%d.h264"
    logging.info(f"Running command: {cmd}")
    os.system(cmd)


def get_packets(frame: Frame, max_data_size: int) -> List[Packet]:
    data_arr: List[str] = frame.to_data_arr(max_data_size=MAX_DATA_SIZE)
    packet_no = 0
    packets: List[Packet] = []
    for data in data_arr:
        yield Packet(
            frame_no=frame.frame_no,
            seq_no=packet_no,
            total_seq_no=len(data_arr),
            size=len(data),
            priority=frame.priority,
            data=data,
        )
        packet_no += 1
    return packets


class VideoStreamServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        logging.info(f"{self.__class__.__name__} initialized")
        self.meta_data = None
        self.total_frames = 0
        super().__init__(*args, **kwargs)

    def send_frames(self, file_path: str, event: events.QuicEvent):
        frame_no = 1  # might need to be 1
        while os.path.exists(f"{file_path}{frame_no}.h264"):  # while frames exist
            frame: Frame = Frame(open(f"{file_path}{frame_no}.h264", "rb").read(), frame_no)
            for p in get_packets(frame, max_data_size=MAX_PKT_SIZE):
                self._quic.send_stream_data(event.stream_id, p.pack(), end_stream=False)
            frame_no += 1

    def quic_event_received(self, event: events.QuicEvent) -> None:
        print(f"QUIC EVENT RECEIVED\tType={type(event)}")
        if isinstance(event, StreamDataReceived):
            data = event.data.decode(ENCODING)
            print(f"Data = {data}")
            query = data.split()
            if query[0] == "GET":
                file_path_mp4: str = f"{FILE_DIR}{query[1]}.mp4"
                if not os.path.exists(file_path_mp4):
                    logging.warning(f"{file_path_mp4} does not exist")
                    self._quic.send_stream_data(event.stream_id,
                                                b"Error: requested file does not exist. Ending connection",
                                                end_stream=True)
                    return

                cl_ffmpeg(file_path_mp4, CACHE_PATH)  # CLI CAll
                self.send_frames(file_path=f"{FILE_DIR}{query[1]}", event=event)
                self._quic.send_stream_data(event.stream_id, b"", end_stream=True)
