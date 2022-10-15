from typing import Iterable
from threading import Semaphore, Event
from asyncio import CancelledError
from winrt.windows.media.capture.frames import MediaFrameSourceGroup, MediaFrameSourceInfo, MediaFrameReader, MediaFrameArrivedEventArgs, MediaFrameSourceKind
from winrt.windows.media.capture import MediaCapture, MediaCaptureInitializationSettings, MediaStreamType, MediaCaptureMemoryPreference, StreamingCaptureMode
from winrt.windows.storage.streams import Buffer
from winrt.windows.security.cryptography import CryptographicBuffer


class VideoCapture:
    """
    VideoCapture(selected_kind: str, selected_type: str, raw_output: bool)

    a VideoCapture object that controls the video capturing process and returns captured frames

    ### Parameters:

    selected_kind: str, the kind of video source you want to use
                    available values are `CUSTOM`,`COLOR`,`INFRARED`,`DEPTH`,`AUDIO`,`IMAGE`,`METADATA`
    selected_type: str, the type of capture mode you want to use
                    available values are `VIDEO_PREVIEW`,`VIDEO_RECORD`,`AUDIO`,`PHOTO`,`METADATA`
    raw_output: bool, control whether to skip black frames

    ...

    ### Attributes:

    options: dict

    current_format: dict

    latest_frame: bytearray

    counters: dict

    ### Methods:

    init()

    start()

    stop()

    frames()

    list_format()

    """

    _formatBits: dict = {"NV12": 12}
    _frame_semaphore: Semaphore = Semaphore(0)
    _stop_event: Event = Event()

    counters = {"frame": 0, "black": 0, "skipped": 0}

    def __init__(
        self,
        selected_kind: str,
        selected_type: str,
        raw_output: bool = False,
        luma_sample: int = 300,
        luma_base: int = 16,
        luma_threshold: int = 16,
        auto_select: bool = True,
        camera_id: int = -1,
    ):
        self.options = {
            "selected_kind": selected_kind,
            "selected_type": selected_type,
            "raw_output": raw_output,
            "luma_sample": luma_sample,
            "luma_base": luma_base,
            "luma_threshold": luma_threshold,
            "auto_select": auto_select,
            "camera_id": camera_id,
        }

    async def start(self):
        try:
            await self._media_frame_reader.start_async()
            self._stop_event.clear()
        except AttributeError:
            print("Please initialize first!")
        except CancelledError:
            self._stop_event.set()
            await self._media_frame_reader.stop_async()
            # Release semaphore to make sure the frame generator won't result in a deadlock
            self._frame_semaphore.release()

    async def stop(self):
        pass

    async def init(self):
        # Select camera
        frame_source_groups = await MediaFrameSourceGroup.find_all_async()
        selected_group = self._select_camera(
            frame_source_groups,
            self.options["selected_kind"],
            camera_id=0 if self.options["auto_select"] else self.options["camera_id"],
        )

        # Initializing capture settings
        settings = MediaCaptureInitializationSettings()
        settings.source_group = selected_group
        settings.memory_preference = MediaCaptureMemoryPreference["CPU"]
        settings.streaming_capture_mode = StreamingCaptureMode["VIDEO"]
        media_capture = MediaCapture()
        await media_capture.initialize_async(settings)
        source_info = self._select_source_info(selected_group, self.options["selected_kind"], self.options["selected_type"])
        self._frame_source = media_capture.frame_sources[source_info.id]
        try:
            self.current_format = {
                "width": self._frame_source.current_format.video_format.width,
                "height": self._frame_source.current_format.video_format.height,
                "fps": self._frame_source.current_format.frame_rate.numerator,
                "type": self._frame_source.current_format.subtype,
            }
        except AttributeError:
            raise AttributeError("Cannot get format infomation!")
        self._media_frame_reader: MediaFrameReader = await media_capture.create_frame_reader_async(self._frame_source)
        self._media_frame_reader.add_frame_arrived(self._frame_arrived_handler)

    def frames(self):
        while not self._stop_event.is_set():
            self._frame_semaphore.acquire()
            yield self.latest_frame

    def __enter__(self):
        from asyncio import new_event_loop, set_event_loop

        self.cam_loop = new_event_loop()
        set_event_loop(self.cam_loop)
        self.cam_loop.run_until_complete(self.init())
        return self.cam_loop

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cam_loop.run_until_complete(self.stop())

    @staticmethod
    def list_format(frame_source):
        for format in frame_source.supported_formats:
            print("Supported formats:")
            print(
                format.major_type,
                "/",
                format.subtype,
                " ",
                str(format.video_format.width),
                "x",
                str(format.video_format.height),
                "@",
                str(format.frame_rate.numerator),
                "fps",
                sep="",
            )
        print("Current format:")
        print(
            frame_source.current_format.major_type,
            "/",
            frame_source.current_format.subtype,
            " ",
            str(frame_source.current_format.video_format.width),
            "x",
            str(frame_source.current_format.video_format.height),
            "@",
            str(frame_source.current_format.frame_rate.numerator),
            "fps",
            sep="",
        )

    def _select_camera(
        self,
        source_groups: Iterable[MediaFrameSourceGroup],
        camera_kind: str,
        camera_id: int = -1,
    ) -> MediaFrameSourceGroup:
        valid_camera = []
        for camera in source_groups:
            for sourceinfo in camera.source_infos:
                if sourceinfo.source_kind == MediaFrameSourceKind[camera_kind]:
                    valid_camera.append(camera)
                    break
        if len(valid_camera) == 0:
            raise IndexError("No valid camera found")
        if len(valid_camera) == 1:
            return valid_camera[0]
        if len(valid_camera) > 1:
            if camera_id < 0 or camera_id >= len(valid_camera):
                raise IndexError("Invalid camera_id selected")
            return valid_camera[camera_id]

    def _select_source_info(self, camera: MediaFrameSourceGroup, camera_kind: str, media_type: str) -> MediaFrameSourceInfo:
        valid_source = []
        for source in camera.source_infos:
            if source.source_kind == MediaFrameSourceKind[camera_kind] and source.media_stream_type == MediaStreamType[media_type]:
                valid_source.append(source)
        if len(valid_source) == 0:
            raise IndexError("No valid source found")
        if len(valid_source) == 1:
            return valid_source[0]
        if len(valid_source) > 1:
            raise IndexError("Error: multiple sources found")

    def _frame_arrived_handler(self, sender: MediaFrameReader, args: MediaFrameArrivedEventArgs) -> None:
        self.counters["frame"] += 1

        # Discard empty frames
        media_frame_reference = sender.try_acquire_latest_frame()
        if media_frame_reference is None:
            self.counters["skipped"] += 1
            return

        # Prepare frame buffer
        buffer_size = (
            self.current_format["width"] * self.current_format["height"] * self._formatBits[self.current_format["type"]] / 8
        )
        if buffer_size.is_integer():
            buffer = Buffer(int(buffer_size))
        else:
            buffer = Buffer(int(buffer_size) + 1)
            raise BytesWarning("Decimal buffer size detected, video data may be currupted")

        # Get image data from frame buffer
        video_media_frame = media_frame_reference.video_media_frame
        software_bitmap = video_media_frame.software_bitmap
        software_bitmap.copy_to_buffer(buffer)
        image_data = CryptographicBuffer.copy_to_byte_array(buffer)

        # Discard black frames
        if not self.options["raw_output"]:
            luma_average = (
                sum(
                    image_data[
                        : int(self.current_format["width"] * self.current_format["height"]) : int(
                            self.current_format["width"] * self.current_format["height"] / self.options["luma_sample"]
                        )
                    ]
                )
                / self.options["luma_sample"]
            )
            if luma_average < self.options["luma_base"] + self.options["luma_threshold"]:
                self.counters["black"] += 1
                return

        self.latest_frame = image_data
        self._frame_semaphore.release()
