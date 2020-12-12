import argparse
import asyncio
import configparser
import logging
import shutil
import signal
import sys
from pathlib import Path

from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration

from src.VideoStreamServerProtocol import VideoStreamServerProtocol

try:
    import uvloop
except ImportError:
    uvloop = None

config = configparser.ConfigParser()
config.read("config.ini")
MAX_DATAGRAM_SIZE = int(config["DEFAULT"]["MaxDatagramSize"])
DEFAULT_LOG_PATH: str = config["SERVER"]["LogPath"]
# LOG_FORMAT: str = config["DEFAULT"]["LogFormat"]
# LOG_DATE_FORMAT: str = config["DEFAULT"]["LogFormat"]
CACHE_PATH: Path = Path(config["SERVER"]["CachePath"])


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)  # set ctrl-c signal

    configuration = QuicConfiguration(
        is_client=False, max_datagram_frame_size=MAX_DATAGRAM_SIZE
    )
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
        "--log",
        type=str,
        default=DEFAULT_LOG_PATH,
        help="file to send logging information to",
    )

    args = parser.parse_args()

    CACHE_PATH.mkdir(parents=True, exist_ok=True)

    # Set Up Logging
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    configuration.load_cert_chain(args.certificate, args.private_key)

    if uvloop is not None:
        uvloop.install()

    loop = asyncio.get_event_loop()
    loop.create_task(
        serve(
            args.host,
            args.port,
            configuration=configuration,
            create_protocol=VideoStreamServerProtocol,
            retry=True,
        )
    )
    logging.info(
        f"Starting Server with VideoStreamServerProtocol on {args.host}:{args.port}"
    )

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    logging.info("Program Terminated")
