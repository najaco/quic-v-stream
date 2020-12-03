import configparser
import logging
import os
from pathlib import Path

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic import events
from aioquic.quic.events import StreamDataReceived
import shutil

config = configparser.ConfigParser()
config.read("config.ini")

CACHE_PATH: Path = Path(config["SERVER"]["CachePath"])
ENCODING = config["DEFAULT"]["Encoding"]

FILES_PATH = Path(config["SERVER"]["FilesPath"])
MAX_DATAGRAM_SIZE = 65536


def cl_ffmpeg(file_path: Path, cache_path: Path, file_prefix: str = ""):
    cache_path.mkdir(parents=True, exist_ok=True)
    if not cache_path.is_dir():
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )
    cmd = f"ffmpeg -i {str(file_path)} -f image2 -c:v copy -bsf h264_mp4toannexb {str(cache_path)}/{file_prefix}%d.h264"
    logging.info(f"Running command: {cmd}")
    os.system(cmd)


class VideoStreamServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def send_frames(self, frames_path: Path, file_name: str, event: events.QuicEvent):
        frame_no = 1  # might need to be 1
        while (frames_path / f"{file_name}{frame_no}.h264").exists():
            logging.info(f"Frame {frame_no} sent ")
            self._quic.send_stream_data(
                event.stream_id,
                data=(frames_path / f"{file_name}{frame_no}.h264").open("rb").read(),
                end_stream=False,
            )
            frame_no += 1
            self.transmit()

    def quic_event_received(self, event: events.QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            data = event.data.decode(ENCODING)
            query = data.split()
            if query[0] == "GET":
                file_path_mp4: Path = FILES_PATH / f"{query[1]}"
                if not file_path_mp4.exists():
                    logging.warning(f"{str(file_path_mp4)} does not exist")
                    self._quic.send_stream_data(
                        event.stream_id,
                        b"Error: requested file does not exist. Ending connection",
                        end_stream=True,
                    )
                    return
                file_no_extension = query[1][0 : query[1].rfind(".")]
                session_cache_path = CACHE_PATH / str(event.stream_id)

                cl_ffmpeg(
                    file_path_mp4, session_cache_path, file_prefix=file_no_extension
                )  # CL Call to ffmpeg
                self.send_frames(
                    frames_path=session_cache_path,
                    file_name=file_no_extension,
                    event=event,
                )
                self._quic.send_stream_data(event.stream_id, b"", end_stream=True)
                logging.info(f"Stream Session {event.stream_id} has ended")
                logging.info(f"Removing {session_cache_path}")
                shutil.rmtree(session_cache_path)  # double check that this works
