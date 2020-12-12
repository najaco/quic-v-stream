import asyncio
import configparser
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Callable, Union

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic import events
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import StreamDataReceived

config = configparser.ConfigParser()
config.read("config.ini")

CACHE_PATH: Path = Path(config["SERVER"]["CachePath"])
ENCODING = config["DEFAULT"]["Encoding"]
FPS: int = int(config["DEFAULT"]["FPS"])

FILES_PATH = Path(config["SERVER"]["FilesPath"])
MAX_DATAGRAM_SIZE = 65536


def cl_ffmpeg(file_path: Path, cache_path: Path, fps: int):
    cache_path.mkdir(parents=True, exist_ok=True)
    if not cache_path.is_dir():
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )
    cmd = f"ffmpeg -i {str(file_path)} -r {fps} -f image2 -c:v copy -bsf h264_mp4toannexb {str(cache_path)}/{file_path.stem}%d.h264"
    logging.info(f"Running command: {cmd}")
    os.system(cmd)


class VideoStreamRequestHandler:
    def __init__(
        self,
        protocol: QuicConnectionProtocol,
        connection: QuicConnection,
        stream_ended: bool,
        stream_id: int,
        transmit: Callable[[], None],
        file_to_serve: Path,
        cache_path: Path,
    ):
        self.protocol = protocol
        self.connection = connection
        self.stream_id = stream_id
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.transmit = transmit
        self.file_to_serve = file_to_serve
        self.cache_path = cache_path

        if stream_ended:
            self.queue.put_nowait({"type": "videostream.request"})

    async def stream(self):
        cl_ffmpeg(
            file_path=self.file_to_serve, cache_path=self.cache_path, fps=FPS
        )  # CL Call to ffmpeg
        await self.send_frames()
        self.connection.send_stream_data(self.stream_id, b"", end_stream=True)
        logging.info(f"Stream Session {self.stream_id} has ended")
        logging.info(f"Removing {self.cache_path}")
        shutil.rmtree(self.cache_path)  # double check that this works

    async def send_frames(self):
        logging.info("Beginning to send frames!")
        file_prefix = self.file_to_serve.stem
        frame_no: int = 1
        file_no: int = 1
        while (self.cache_path / f"{file_prefix}{file_no}.h264").exists():
            await asyncio.sleep(1 / FPS)
            with (self.cache_path / f"{file_prefix}{file_no}.h264").open("rb") as frame:
                data = frame.read()
                for i in range(0, data.count(b"\x00\x00\x01")):
                    logging.info(
                        f"Frame {frame_no} sent at {int(time.time() * 1000)}ms"
                    )
                    frame_no += 1
                self.connection.send_stream_data(self.stream_id, data=data)
            file_no += 1
            self.transmit()


Handler = Union[VideoStreamRequestHandler]


class VideoStreamServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handlers: Dict[int, Handler] = {}

    def quic_event_received(self, event: events.QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            data = event.data.decode(ENCODING)
            query = data.split()
            if query[0] == "GET":
                file_to_serve: Path = FILES_PATH / f"{query[1]}"
                if not file_to_serve.exists():
                    logging.warning(f"{str(file_to_serve)} does not exist")
                    self._quic.send_stream_data(
                        event.stream_id,
                        b"Error: requested file does not exist. Ending connection",
                        end_stream=True,
                    )
                    return
                session_cache_path = CACHE_PATH / str(event.stream_id)

                handler = VideoStreamRequestHandler(
                    connection=self._quic,
                    protocol=self,
                    stream_ended=False,
                    stream_id=event.stream_id,
                    transmit=self.transmit,
                    file_to_serve=file_to_serve,
                    cache_path=session_cache_path,
                )
                self._handlers[event.stream_id] = handler
                asyncio.ensure_future(handler.stream())
