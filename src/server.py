import argparse
import asyncio
import configparser
import logging
import shutil
import signal
from pathlib import Path
from typing import Dict, Optional
import sys

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import ProtocolNegotiated, QuicEvent, StreamDataReceived
from aioquic.tls import SessionTicket
import os
from src.VideoStreamServerProtocol import VideoStreamServerProtocol
from src.objs import Frame

try:
    import uvloop
except ImportError:
    uvloop = None

HOST = '127.0.0.1'
PORT = 40205
LOG_LOCATION = './logs/'
FILE_DIR = "./assets/"
ENCODING = "ascii"
MAX_DATAGRAM_SIZE = 65536
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


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


def cl_ffmpeg(file_path: str, cache_path: str):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )
    cmd = "ffmpeg -i {} -f image2 -c:v copy -bsf h264_mp4toannexb {}%d.h264".format(
        file_path, cache_path
    )
    os.system(cmd)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)

    Path(LOG_LOCATION).mkdir(parents=True, exist_ok=True)  # create directory if it does not exist
    Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=f'{LOG_LOCATION}{config["SERVER"]["LogPath"]}', level=logging.INFO)

    configuration = QuicConfiguration(is_client=False, max_datagram_frame_size=MAX_DATAGRAM_SIZE)
    parser = argparse.ArgumentParser(description="QUIC VideoStreamServer server")
    parser.add_argument(
        "app",
        type=str,
        nargs="?",
        default="demo:app",
        help="the ASGI application as <module>:<attribute>",
    )
    parser.add_argument(
        "-c",
        "--certificate",
        type=str,
        required=True,
        help="load the TLS certificate from the specified file",
    )
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
        "-k",
        "--private-key",
        type=str,
        required=True,
        help="load the TLS private key from the specified file",
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    args = parser.parse_args()

    configuration.load_cert_chain(args.certificate, args.private_key)

    if uvloop is not None:
        uvloop.install()
    loop = asyncio.get_event_loop()
    loop.create_task(
        serve(
            HOST,
            PORT,
            configuration=configuration,
            create_protocol=VideoStreamServerProtocol,
            retry=True,
        )
    )
    logging.info("About to run server")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
