# Copyright 2022-2024 PufferOverflow <puffer@puffer.moe>
# SPDX-License-Identifier: MPL-1.1
#
# The contents of this file are subject to the Mozilla Public License
# Version 1.1 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# https://www.mozilla.org/MPL/1.1/

from typing import Iterable
from threading import Event
from asyncio import events
from winrt.windows.media.capture.frames import MediaFrameSourceGroup, MediaFrameSourceInfo, MediaFrameReader, MediaFrameArrivedEventArgs, MediaFrameSourceKind
from winrt.windows.media.capture import MediaCapture, MediaCaptureInitializationSettings, MediaStreamType, MediaCaptureMemoryPreference, StreamingCaptureMode
from winrt.windows.storage.streams import Buffer
from winrt.windows.security.cryptography import CryptographicBuffer
from collections import Counter


class VideoCapture:

    _formatBits: dict = {"NV12": 12}
    _frame_event: Event = Event()
    _stop_event: Event = Event()

    frame_counter = Counter()

    @staticmethod
    def wait(afunc):
        loop = events.new_event_loop()
        events.set_event_loop(loop)
        result = loop.run_until_complete(afunc)
        events.set_event_loop(None)
        loop.close()
        return result

    def start(self):
        self._media_frame_reader.start_async()
        self._stop_event.clear()
        print("capture started")

    def stop(self):
        self._stop_event.set()
        self._media_frame_reader.stop_async()
        print("capture stopped")
        # Release semaphore to make sure the frame generator won't result in a deadlock
        self._frame_event.set()

    def __init__(self, options = dict()):
        self.options = options

        frame_source_groups = self.wait(MediaFrameSourceGroup.find_all_async())
        selected_group = self._select_camera(frame_source_groups, self.options)

        # Initializing capture settings
        settings = MediaCaptureInitializationSettings()
        settings.source_group = selected_group
        settings.memory_preference = MediaCaptureMemoryPreference["CPU"]
        settings.streaming_capture_mode = StreamingCaptureMode["VIDEO"]
        media_capture = MediaCapture()
        self.wait(media_capture.initialize_async(settings))
        source_info = self._select_source_info(selected_group, self.options)
        self._frame_source = media_capture.frame_sources[source_info.id]
        try:
            self.current_format = {
                "width": self._frame_source.current_format.video_format.width,
                "height": self._frame_source.current_format.video_format.height,
                "fps": self._frame_source.current_format.frame_rate.numerator,
                "type": self._frame_source.current_format.subtype,
            }
            self._buffer_size = self.current_format["width"] * self.current_format["height"] * self._formatBits[self.current_format["type"]] / 8
            self._buffer_size = int(self._buffer_size) if self._buffer_size.is_integer() else int(self._buffer_size) + 1
            self._frame_pixel_number = int(self.current_format["width"] * self.current_format["height"])
            self._pixel_sample_interval = int(self.current_format["width"] * self.current_format["height"] / int(self.options["option_luma_sample"]))
            self._pixel_sample_number = int(self.options["option_luma_sample"])

        except AttributeError:
            raise AttributeError("Cannot get format infomation!")
        
        self._media_frame_reader: MediaFrameReader = self.wait(media_capture.create_frame_reader_async(self._frame_source))

        self._media_frame_reader.add_frame_arrived(self._frame_arrived_handler)

    def get_frame(self):
        print("wait for frame")
        while not self._stop_event.is_set():
            self._frame_event.wait()
            self._frame_event.clear()
            print("frame out")
            yield self.latest_frame

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

    def _select_camera(self, source_groups: Iterable[MediaFrameSourceGroup], options) -> MediaFrameSourceGroup:
        valid_camera = []
        camera_kind = options["camera_kind"] if "camera_kind" in options else "INFRARED"
        for camera in source_groups:
            for sourceinfo in camera.source_infos:
                if sourceinfo.source_kind == MediaFrameSourceKind[camera_kind]:
                    valid_camera.append(camera)
                    break
        if len(valid_camera) > 0:
            camera_id = options["camera_id"] if "camera_id" in options else 0
            return valid_camera[camera_id]
        else:
            raise IndexError("No valid camera found")

    def _select_source_info(self, camera: MediaFrameSourceGroup, options) -> MediaFrameSourceInfo:
        valid_source = []
        camera_kind = options["camera_kind"] if "camera_kind" in options else "INFRARED"
        media_type = options["media_type"] if "media_type" in options else "VIDEO_RECORD"
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
        # print('frame arrived')
        # Discard empty frames
        media_frame_reference = sender.try_acquire_latest_frame()
        if media_frame_reference is None:
            self.frame_counter["empty"] += 1
            return

        # Prepare frame buffer
        buffer = Buffer(self._buffer_size)

        # Get image data from frame buffer
        video_media_frame = media_frame_reference.video_media_frame
        software_bitmap = video_media_frame.software_bitmap
        software_bitmap.copy_to_buffer(buffer)
        image_data = CryptographicBuffer.copy_to_byte_array(buffer)

        # Discard black frames
        if not self.options["option_luma_auto"]:
            luma_average = (sum(image_data[:self._frame_pixel_number:self._pixel_sample_interval]) / self._pixel_sample_number)
            if luma_average < self.options["option_luma_base"] + self.options["option_luma_threshold"]:
                self.frame_counter["black"] += 1
                return

        self.latest_frame = image_data
        self.frame_counter["good"] += 1
        print("frame processing done")
        self._frame_event.set()
