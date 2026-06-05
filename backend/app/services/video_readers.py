"""Единый слой чтения кадров из видеоисточников.

Остальные сервисы не должны знать, как именно открыт источник: это может быть
локальный MP4-файл для демонстрации или live-поток камеры. Этот модуль прячет
детали PyAV и отдаёт всем потребителям одинаковый результат: BGR-кадр OpenCV и
timestamp кадра, если библиотека смогла его определить.

Такое разделение нужно для сопровождения проекта. Если позже появится другой
способ чтения видео, например OpenCV VideoCapture или аппаратный decoder, его
можно добавить здесь, не переписывая stream_manager, анализ видео и анализ
маршрута гостя.
"""

from __future__ import annotations

import queue
import threading

import numpy as np

try:
    import av
except Exception:
    av = None


class BaseFrameReader:
    """Базовый интерфейс reader-а кадров.

    Сервисы работают только с этим контрактом: можно прочитать следующий кадр,
    закрыть источник и при возможности узнать fps или количество кадров. Реальная
    реализация сейчас одна — ``PyAVFrameReader``, но интерфейс оставляет место
    для замены backend-а чтения видео.
    """

    backend_name = "base"

    def read(self) -> tuple[np.ndarray, float | None] | None:
        """Вернуть следующий кадр или ``None``, если источник закончился/недоступен."""

        raise NotImplementedError

    def close(self) -> None:
        """Освободить ресурсы источника видео."""

        raise NotImplementedError

    @property
    def fps(self) -> float | None:
        """Вернуть частоту кадров, если источник её сообщает."""

        return None

    @property
    def frame_count(self) -> int | None:
        """Вернуть количество кадров, если это не live-поток и значение известно."""

        return None


class PyAVFrameReader(BaseFrameReader):
    """Reader кадров на базе PyAV.

    PyAV используется как обёртка над FFmpeg. Для сохранённых файлов кадры
    читаются последовательно в текущем потоке. Для live-потоков запускается
    отдельный поток чтения с очередью на один кадр: если frontend или анализ
    временно не успевает, старый кадр выбрасывается, а потребитель получает
    самый свежий кадр. Это важнее для видеонаблюдения, чем обработать абсолютно
    каждый кадр с задержкой.
    """

    backend_name = "pyav"

    def __init__(self, source: str, is_live: bool = False):
        """Открыть файл или live-поток и подготовить decoder.

        Параметры:
            source: путь к файлу или URL потока, который пришёл из настроек
                камеры или задания анализа.
            is_live: признак live-источника. Для него применяются более короткие
                таймауты и отдельный поток чтения.

        Ошибки:
            RuntimeError: PyAV не установлен, источник не открылся или в нём нет
                видеопотока. Такие ошибки выше превращаются в предупреждение
                камеры или статус failed у задания анализа.
        """

        if av is None:
            raise RuntimeError("PyAV is not installed")

        self.container = self._open_container(source, is_live)
        if not self.container.streams.video:
            raise RuntimeError("Video stream not found in source")

        self.video_stream = self.container.streams.video[0]
        try:
            self.video_stream.thread_type = "AUTO"
        except Exception:
            pass

        self._iterator = self.container.decode(video=0)
        self._is_live = is_live

        if self._is_live:
            self._q = queue.Queue(maxsize=1)
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._reader_thread, daemon=True)
            self._thread.start()

    def _open_container(self, source: str, is_live: bool):
        """Открыть контейнер PyAV с настройками, подходящими типу источника.

        Для live RTSP используется несколько попыток: сначала TCP и параметры,
        которые уменьшают ожидание повреждённых кадров, затем более простой
        fallback. Это делает подключение терпимее к учебным/демо-камерам, где
        поток может быть нестабильным.
        """

        attempts: list[tuple[dict[str, str] | None, float | tuple[float, float] | None]] = [(None, None)]

        if is_live:
            common_options = {
                "fflags": "discardcorrupt",
                "probesize": "131072",
                "analyzeduration": "1000000",
                "rw_timeout": "5000000",
                "stimeout": "5000000",
                "max_delay": "300000",
            }
            timeout: float | tuple[float, float] | None = 2.0

            if source.startswith("rtsp://"):
                attempts = [
                    ({**common_options, "rtsp_transport": "tcp"}, timeout),
                    ({"rtsp_transport": "tcp"}, timeout),
                    (None, timeout),
                ]
            else:
                attempts = [(common_options, timeout), (None, timeout)]

        last_error: Exception | None = None
        for options, timeout in attempts:
            try:
                return av.open(source, mode="r", options=options, timeout=timeout)
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise RuntimeError(str(last_error)) from last_error
        raise RuntimeError("Unable to open video source")

    def _reader_thread(self):
        """Фоново читать live-поток и хранить только самый свежий кадр.

        Очередь имеет размер 1 специально: для камеры наблюдения старый кадр
        через несколько секунд уже не нужен. Если очередь занята, предыдущий
        кадр удаляется, и на его место кладётся новый.
        """

        try:
            for frame in self._iterator:
                if self._stop_event.is_set():
                    break
                if getattr(frame, "is_corrupt", False):
                    continue

                array = frame.to_ndarray(format="bgr24")
                timestamp = float(frame.time) if frame.time is not None else None

                if self._q.full():
                    try:
                        self._q.get_nowait()
                    except queue.Empty:
                        pass

                self._q.put((array, timestamp))
        except Exception:
            pass
        finally:
            try:
                self.container.close()
            except Exception:
                pass

    def read(self) -> tuple[np.ndarray, float | None] | None:
        """Прочитать следующий доступный кадр в формате BGR.

        Для live-потока функция ждёт свежий кадр из очереди. Для файла она
        последовательно декодирует кадры и пропускает повреждённые. Возвращаемый
        timestamp используется в demo-видео, чтобы воспроизводить запись с
        правильной скоростью и строить события маршрута по времени внутри MP4.
        """

        if self._is_live:
            try:
                return self._q.get(timeout=5.0)
            except queue.Empty:
                return None

        while True:
            try:
                frame = next(self._iterator)
            except StopIteration:
                return None
            except av.error.EOFError:
                return None
            except Exception as exc:
                raise RuntimeError(str(exc)) from exc

            if getattr(frame, "is_corrupt", False):
                continue

            array = frame.to_ndarray(format="bgr24")
            timestamp = float(frame.time) if frame.time is not None else None
            return array, timestamp

    def close(self) -> None:
        """Остановить чтение и закрыть контейнер FFmpeg/PyAV."""

        if getattr(self, "_is_live", False):
            self._stop_event.set()
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
            try:
                self.container.close()
            except Exception:
                pass
            return

        try:
            self.container.close()
        except Exception:
            pass

    @property
    def fps(self) -> float | None:
        """Получить fps видеопотока, если PyAV смог его определить."""

        try:
            rate = self.video_stream.average_rate
            return float(rate) if rate else None
        except Exception:
            return None

    @property
    def frame_count(self) -> int | None:
        """Получить число кадров для файлового видео.

        Для live-камер это значение не имеет смысла, поэтому возвращается
        ``None``. Для MP4 оно используется в прогрессе анализа видео.
        """

        if self._is_live:
            return None
        try:
            value = int(self.video_stream.frames)
            return value if value > 0 else None
        except Exception:
            return None


def create_frame_reader(source: str, is_live: bool = False) -> BaseFrameReader:
    """Создать reader кадров для указанного источника.

    Сейчас фабрика всегда возвращает ``PyAVFrameReader``. Наличие отдельной
    функции полезно, потому что все сервисы вызывают именно её: при замене
    библиотеки чтения видео не придётся искать создание reader-а по всему
    проекту.
    """

    if av is None:
        raise RuntimeError("PyAV is not installed.")
    return PyAVFrameReader(source, is_live=is_live)
