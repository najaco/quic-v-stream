import argparse
import asyncio
import configparser
import logging
import shutil
import signal
import ssl
import sys
from pathlib import Path
from typing import cast, Optional, Dict

from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration

from src.objs.frame_builder import FrameBuilder

try:
    import uvloop
except ImportError:
    uvloop = None

config = configparser.ConfigParser()
config.read("config.ini")

CACHE_PATH: str = config["CLIENT"]["CachePath"]
ENCODING: str = config["DEFAULT"]["Encoding"]
FILE_WAIT_TIME: float = float(config["CLIENT"]["FileWaitTime"])
FILE_MAX_WAIT_TIME: float = float(config["CLIENT"]["FileMaxWaitTime"])
LOG_PATH: Path = Path(config["CLIENT"]["LogPath"])
MAX_DATAGRAM_SIZE = int(config["DEFAULT"]["MaxDatagramSize"])


class VideoStreamClientProtocol(QuicConnectionProtocol):
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
                sys.stdout.buffer.write(event.data)


async def run(config: QuicConfiguration, host: str, port: int, requested_video: str) -> None:
    async with connect(host=host, port=port, configuration=config, create_protocol=VideoStreamClientProtocol) as client:
        client = cast(VideoStreamClientProtocol, client)
        await client.send_request_for_video(requested_video)


def clean_up(sig, frame):
    logging.info(f"Skipping Removal of {CACHE_PATH}")
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)  # create directory if it does not exist
    Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(LOG_PATH), level=logging.INFO)

    defaults = QuicConfiguration(is_client=True, max_datagram_frame_size=MAX_DATAGRAM_SIZE)

    parser = argparse.ArgumentParser(description="QUIC Video Stream client")
    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4433,
        help="listen on the specified port (defaults to 4433)",
    )
    parser.add_argument(
        "-r",
        "--request",
        type=str,
        default="",
        help="Video to request",
    )
    args = parser.parse_args()

    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = ssl.CERT_NONE

    if uvloop is not None:
        uvloop.install()

    logging.info("Starting Client with VideoStreamClientProtocol")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(config=configuration, host=args.host, port=args.port, requested_video=args.request)
    )
