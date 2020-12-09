import argparse
import asyncio
import configparser
import logging
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import cast, Optional

from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration

try:
    import uvloop
except ImportError:
    uvloop = None

config = configparser.ConfigParser()
config.read("config.ini")

ENCODING: str = config["DEFAULT"]["Encoding"]
FILE_WAIT_TIME: float = float(config["CLIENT"]["FileWaitTime"])
FILE_MAX_WAIT_TIME: float = float(config["CLIENT"]["FileMaxWaitTime"])
DEFAULT_LOG_PATH: str = str(config["CLIENT"]["LogPath"])
# LOG_FORMAT: str = config["DEFAULT"]["LogFormat"]
# LOG_DATE_FORMAT: str = config["DEFAULT"]["LogFormat"]
MAX_DATAGRAM_SIZE = int(config["DEFAULT"]["MaxDatagramSize"])


def get_vlc_path_for_current_platform(platform: str = sys.platform) -> Path:
    if platform == "linux" or platform == "linux2":
        return Path('vlc')
    elif platform == "darwin":
        return Path('/Applications/VLC.app/Contents/MacOS/VLC')
    elif platform == "win32":
        return Path('%PROGRAMFILES%\\VideoLAN\\VLC\\vlc.exe')

class VideoStreamClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future[None]] = None
        self.count = 0
        self.vlc_process = None

    async def send_request_for_video(self, filename: str) -> None:
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(
            stream_id, f"GET {filename}".encode(ENCODING), end_stream=False
        )
        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()
        vlc_path: Path = get_vlc_path_for_current_platform()
        if not vlc_path.exists():
            logging.error(f"vlc was not found at {str(vlc_path)}")
            return
        self.vlc_process = subprocess.Popen(
            [str(vlc_path), "--demux", "h264", "-"],
            stdin=subprocess.PIPE,
        )
        return await asyncio.shield(waiter)

    def quic_event_received(self, event: events.QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, events.StreamDataReceived):
                # logging.info(f"StreamDataReceived: {self.count}\t LEN = {len(event.data)}")
                if event.end_stream:
                    waiter = self._ack_waiter
                    self._ack_waiter = None
                    waiter.set_result(None)
                    logging.info(f"End Stream Detected")
                    return
                for i in range(0, event.data.count(b"\x00\x00\x01")):
                # if b"\x00\x00\x01" in event.data:
                    self.count += 1
                    logging.info(f"Detected Beginning of Frame: {self.count} at {int(time.time() * 1000)}ms")
                self.vlc_process.stdin.write(event.data)


async def run(
        config: QuicConfiguration, host: str, port: int, requested_video: str
) -> None:
    async with connect(
            host=host,
            port=port,
            configuration=config,
            create_protocol=VideoStreamClientProtocol,
    ) as client:
        client = cast(VideoStreamClientProtocol, client)
        await client.send_request_for_video(requested_video)


def clean_up(sig, frame):
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)

    defaults = QuicConfiguration(
        is_client=True, max_datagram_frame_size=MAX_DATAGRAM_SIZE
    )

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
        "-r", "--request", type=str, default="", help="Video to request",
    )
    parser.add_argument(
        "-l",
        "--log",
        type=str,
        default=DEFAULT_LOG_PATH,
        help="file to send logging information to",
    )

    args = parser.parse_args()

    # Set Up Logging
    # Set Up Logging
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    configuration = QuicConfiguration(is_client=True)
    configuration.verify_mode = ssl.CERT_NONE

    if uvloop is not None:
        uvloop.install()

    logging.info("Starting Client with VideoStreamClientProtocol")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(
            config=configuration,
            host=args.host,
            port=args.port,
            requested_video=args.request,
        )
    )
    logging.info("Program Terminated")
