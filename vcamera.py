# Copyright 2022-2024 PufferOverflow <puffer@puffer.moe>
# SPDX-License-Identifier: MPL-1.1
#
# The contents of this file are subject to the Mozilla Public License
# Version 1.1 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# https://www.mozilla.org/MPL/1.1/

from videocapture import VideoCapture
from threading import Thread, Event
from pyvirtualcam import Camera as virtualCamera
from pyvirtualcam.camera import PixelFormat
from numpy import frombuffer, uint8


class vcamera(Thread):
    def __init__(self, options):
        Thread.__init__(self)
        self.options = options
        self._stop_event = Event()
        self.format_dict = {"NV12": PixelFormat.NV12}

    def run(self):
        print("vcam starting")
        # Start video capturing loop
        self.capture_ctrl = VideoCapture(self.options)
        # Start virtual camera loop
        with virtualCamera(
            width=self.capture_ctrl.current_format["width"] if self.options['option_vcam_width_auto'] else self.options['option_vcam_width'],
            height=self.capture_ctrl.current_format["height"] if self.options['option_vcam_height_auto'] else self.options['option_vcam_height'],
            fps=self.options['option_vcam_fps'],
            fmt=self.format_dict[self.capture_ctrl.current_format["type"] if self.options['option_vcam_pixel_format'].value == 'auto' else self.options['option_vcam_pixel_format']['value']],
            backend="unitycapture",
            print_fps=True,
        ) as vcam:
            print("vcam started")
            self.capture_ctrl.start()
            for frame in self.capture_ctrl.get_frame():
                if self._stop_event.is_set():
                    self.capture_ctrl.stop()
                    break
                print("update frame")
                vcam.send(frombuffer(bytes(frame), uint8))
            print("vcam stopped")

    def stop(self):
        print("vcam stoping")
        self._stop_event.set()