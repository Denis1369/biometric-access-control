from __future__ import annotations

import numpy as np

try:
    import av  # type: ignore
except Exception:  # pragma: no cover - optional dependency import safety
    av = None


class BaseFrameReader:
    backend_name = "base"

    def read(self) -> tuple[np.ndarray, float | None] | None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    @property
    def fps(self) -> float | None:
        return None

    @property
    def frame_count(self) -> int | None:
        return None


class PyAVFrameReader(BaseFrameReader):
    backend_name = "pyav"

    def __init__(self, source: str, is_live: bool = False):
        if av is None:
            raise RuntimeError("PyAV не установлен")

        options: dict[str, str] = {}
        timeout: float | tuple[float, float] | None = None

        if is_live and source.startswith("rtsp://"):
            options = {
                "rtsp_transport": "tcp",
                "fflags": "nobuffer",
                "flags": "low_delay",
                "probesize": "32768",
                "analyzeduration": "0",
                "rw_timeout": "2000000",
            }
            timeout = 2.0

        self.container = av.open(source, mode="r", options=options or None, timeout=timeout)
        if not self.container.streams.video:
            raise RuntimeError("Во входном источнике нет видеопотока")

        self.video_stream = self.container.streams.video[0]
        try:
            self.video_stream.thread_type = "SLICE"
        except Exception:
            pass
        self._iterator = self.container.decode(video=0)
        self._is_live = is_live

    def read(self) -> tuple[np.ndarray, float | None] | None:
        try:
            frame = next(self._iterator)
        except StopIteration:
            return None
        except av.error.EOFError:
            return None
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        array = frame.to_ndarray(format="bgr24")
        timestamp = float(frame.time) if frame.time is not None else None
        return array, timestamp

    def close(self) -> None:
        try:
            self.container.close()
        except Exception:
            pass

    @property
    def fps(self) -> float | None:
        try:
            rate = self.video_stream.average_rate
            return float(rate) if rate else None
        except Exception:
            return None

    @property
    def frame_count(self) -> int | None:
        if self._is_live:
            return None
        try:
            value = int(self.video_stream.frames)
            return value if value > 0 else None
        except Exception:
            return None


def create_frame_reader(source: str, is_live: bool = False) -> BaseFrameReader:
    if av is None:
        raise RuntimeError("PyAV не установлен. Установи пакет av через pip install av")
    return PyAVFrameReader(source, is_live=is_live)
