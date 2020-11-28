import argparse
import configparser
import shutil
import signal
import ssl

import asyncio
import logging
import sys
from pathlib import Path
from typing import cast, Optional, Dict
import time
from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
import os

from src.objs import Metadata
from src.objs.packet import Packet
from src.objs.packet import Frame
from src.objs.frame_builder import FrameBuilder

try:
    import uvloop
except ImportError:
    uvloop = None

config = configparser.ConfigParser()
config.read("config.ini")
MAX_PKT_SIZE: int = int(config["DEFAULT"]["MaxPacketSize"])
PRIORITY_THRESHOLD: Frame.Priority = Frame.Priority(
    int(config["DEFAULT"]["PriorityThreshold"])
)
CACHE_PATH: str = config["CLIENT"]["CachePath"]
FILE_WAIT_TIME: float = float(config["CLIENT"]["FileWaitTime"])
FILE_MAX_WAIT_TIME: float = float(config["CLIENT"]["FileMaxWaitTime"])

HOST = '127.0.0.1'
PORT = 40205
LOG_LOCATION = './logs/'
MAX_DATAGRAM_SIZE = 65536
ENCODING = "ascii"
REQUESTED_FILE_NAME = "bus"


def reader(meta_data: Metadata):
    logging.info("Reader Started")
    frame_no = 1
    while not os.path.exists("{}{}.h264".format(CACHE_PATH, 1)):
        time.sleep(FILE_WAIT_TIME)
    while frame_no < meta_data.number_of_frames:
        logging.info("Waiting for {}{}.h264 exists".format(CACHE_PATH, frame_no))
        time_passed = 0
        while not os.path.exists("{}{}.h264".format(CACHE_PATH, frame_no)) and (
                time_passed < FILE_MAX_WAIT_TIME
        ):
            time_passed += FILE_WAIT_TIME
            time.sleep(FILE_WAIT_TIME)  # force context switch

        if not os.path.exists(
                "{}{}.h264".format(CACHE_PATH, frame_no)
        ):  # skip if frame does not exist
            logging.warning("Skipping Frame {}".format(frame_no))
            frame_no += 1
            continue

        with open("{}{}.h264".format(CACHE_PATH, frame_no), "rb") as f:
            with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                stdout.write(f.read())
                stdout.flush()
        logging.info("Wrote {}{}.h264".format(CACHE_PATH, frame_no))
        os.remove("{}{}.h264".format(CACHE_PATH, frame_no))
        frame_no += 1
    logging.info("Reader Finished")


class StreamClient(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future[None]] = None
        self.frames: Dict[int, FrameBuilder] = {}

    async def send_request_for_video(self, filename: str) -> None:
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, f"GET {filename}".encode(ENCODING), end_stream=False)
        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()
        # CREATE THREAD FOR READING AND PRINTING TO STDOUT

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: events.QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, events.StreamDataReceived):
                if event.end_stream:
                    waiter = self._ack_waiter
                    self._ack_waiter = None
                    waiter.set_result(None)
                    logging.info(f"Data received = {event.data}")
                    return

                p = Packet.unpack(event.data)
                if p.frame_no not in self.frames:
                    self.frames[p.frame_no] = FrameBuilder(
                        n_expected_packets=p.total_seq_no, priority=p.priority
                    )
                try:
                    self.frames[p.frame_no].emplace(p.seq_no, p.data)
                except Exception:
                    print("Error with frame no {}".format(p.frame_no))
                    # check if frame is filled
                if self.frames[p.frame_no].is_complete():
                    with open(f"{CACHE_PATH}{p.frame_no}.h264", "wb+") as frame_file:
                        frame_file.write(self.frames[p.frame_no].get_data_as_bytes())
                    del self.frames[p.frame_no]  # delete frame now that it has been saved


async def run(config: QuicConfiguration, host, port) -> None:
    async with connect(host=host, port=port, configuration=config, create_protocol=StreamClient) as client:
        client = cast(StreamClient, client)
        await client.send_request_for_video(REQUESTED_FILE_NAME)


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)
    Path(LOG_LOCATION).mkdir(parents=True, exist_ok=True)  # create directory if it does not exist
    Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=f'{LOG_LOCATION}{config["CLIENT"]["LogPath"]}', level=logging.INFO)
    logging.info(config)

    defaults = QuicConfiguration(is_client=True, max_datagram_frame_size=MAX_DATAGRAM_SIZE)

    parser = argparse.ArgumentParser(description="QUIC Video Stream client")
    # prepare configuration
    configuration = QuicConfiguration(is_client=True)

    configuration.verify_mode = ssl.CERT_NONE
    if uvloop is not None:
        uvloop.install()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(
        run(config=configuration, host=HOST, port=PORT)
    )
