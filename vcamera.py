from videocapture import VideoCapture
from threading import Thread
from pyvirtualcam import Camera as virtualCamera
from pyvirtualcam.camera import PixelFormat
from numpy import frombuffer, uint8


class vCamera(Thread):
    def run(self):

        # Start video capturing loop
        self.capture_ctrl = VideoCapture("INFRARED", "VIDEO_RECORD")
        with self.capture_ctrl as self.capture_loop:
            self.task = self.capture_loop.create_task(self.capture_ctrl.start())
            self.capture_loop.run_forever()
            # Start virtual camera loop
            format_dict = {"NV12": PixelFormat.NV12}
            with virtualCamera(
                width=self.capture_ctrl.current_format["width"],
                height=self.capture_ctrl.current_format["height"],
                fps=30,
                fmt=format_dict[self.capture_ctrl.current_format["type"]],
                backend="unitycapture",
                print_fps=True,
            ) as vcam:
                for frame in self.capture_ctrl.frames():
                    vcam.send(frombuffer(bytes(frame), uint8))
                    vcam.sleep_until_next_frame()

    def stop(self):
        self.task.cancel()

    @staticmethod
    def show_stats(stop_event, counters, format):
        from time import sleep, perf_counter
        from copy import deepcopy

        prev_counters = {"frame": 0, "black": 0, "skipped": 0}
        while not stop_event.is_set():
            time_keeper = perf_counter()
            current_counters = deepcopy(counters)
            captured_frames = current_counters["frame"] - prev_counters["frame"]
            black_frames = current_counters["black"] - prev_counters["black"]
            skipped_frames = current_counters["skipped"] - prev_counters["skipped"]
            normal_frames = captured_frames - black_frames - skipped_frames
            prev_counters = current_counters
            print(f"captured frames: {captured_frames}/{format['fps']}")
            print(f"normal frames: {normal_frames}/{captured_frames}")
            print(f"black frames: {black_frames}/{captured_frames}")
            print(f"skipped frames: {skipped_frames}/{captured_frames}\n")
            sleep(1 + time_keeper - perf_counter())


if __name__ == "__main__":
    from time import sleep

    test = vCamera()
    print("Test start")
    test.start()
    sleep(3)
    print("Test stop")
    test.stop()
