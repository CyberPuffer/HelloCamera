# Copyright 2022-2024 PufferOverflow <puffer@puffer.moe>
# SPDX-License-Identifier: MPL-1.1
#
# The contents of this file are subject to the Mozilla Public License
# Version 1.1 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# https://www.mozilla.org/MPL/1.1/

import toga
from toga.style.pack import COLUMN, Pack
from toga.constants import *
from vcamera import vcamera

class NumberInput(toga.NumberInput):
    def __init__(self,
            id=None,
            style=None,
            step = 1,
            min = None,
            max = None,
            value = None,
            enabled = True,
            readonly = False,
            on_change = None,
            min_value = None,  # DEPRECATED
            max_value = None,  # DEPRECATED
        ):
        super().__init__(id=id, style=style, step=step, min=min, max=max, value=value, readonly=readonly, on_change=on_change, min_value=min_value, max_value=max_value)
        self._impl.set_enabled(enabled)

def get_options(app, **kwargs):
    return {widget_name:widget.value for widget_name,widget in app.widgets.items() if widget_name.startswith("option_")}

def toggle_base_widget_state(widget, **kwargs):
    widget_base_id = "_".join(widget.id.split("_")[:-1])
    widget.window.widgets[widget_base_id].enabled = not widget.window.widgets[widget_base_id].enabled

def toggle_child_widget_state(widget, **kwargs):
    widget_base_id = "_".join(widget.id.split("_")[:-1])
    widget_list = [widget.window.widgets[widget_name] for widget_name in widget.window.widgets.keys() if widget_name.startswith(widget_base_id) and widget_name != widget.id]
    widget_base_id = "_".join(widget.id.split("_")[:-1])
    for widget in widget_list:
        widget.enabled = not widget.enabled

def start_handler(widget, **kwargs):
    options = get_options(widget.app)
    if not hasattr(widget.app, 'camera_controller'):
        print("init controller")
        widget.app.camera_controller = vcamera(options = options)
        widget.app.camera_controller.start()

def stop_handler(widget, **kwargs):
    if hasattr(widget.app, 'camera_controller'):
        widget.app.camera_controller.stop()
        del widget.app.camera_controller

def stats_handler(widget, **kwargs):
    pass

def build(app):
    print("App Start")
    inline_style = Pack(padding=(0,20))
    short_sep_style = Pack(padding=(0,5,0,0))
    sep_style = Pack(padding=(0,20,0,0))
    padding_style = Pack(padding=(20))
    verticle_style = Pack(direction=COLUMN, flex=1)

    vcam_label = toga.Label(text="Virtual camera configuration",style=padding_style)
    vcam_section = toga.Box(
        children = [
            vcam_width_label := toga.Label("Width:"), vcam_width_input := NumberInput(id="option_vcam_width", enabled=False, min=0,style=short_sep_style), vcam_width_auto_switch := toga.Switch(id="option_vcam_width_auto",text="Auto", value=True, on_change=toggle_base_widget_state,style=sep_style),
            vcam_height_label := toga.Label("Height:"), vcam_height_input := NumberInput(id="option_vcam_height", enabled=False, min=0,style=short_sep_style), vcam_height_auto_switch := toga.Switch(id="option_vcam_height_auto",text="Auto", value=True, on_change=toggle_base_widget_state,style=sep_style),
            vcam_fps_label := toga.Label("Target frame rate:"),
            vcam_fps_input := NumberInput(id="option_vcam_fps", value=30, min=0,style=sep_style),
            vcam_pixel_format_label := toga.Label("Pixel Format:"), vcam_pixel_format_selection := toga.Selection(
                items=[
                    {"name": "Auto", "value": "auto"},
                    {"name": "BGR",  "value": "24BG"},
                    {"name": "GRAY", "value": "J400"},
                    {"name": "I420", "value": "I420"},
                    {"name": "NV12", "value": "NV12"},
                    {"name": "RGB",  "value": "raw "},
                    {"name": "RGBA", "value": "ABGR"},
                    {"name": "UYVY", "value": "UYVY"},
                    {"name": "YUYV", "value": "YUY2"},
                ],
                id="option_vcam_pixel_format",
                accessor="name",
                style=sep_style
            )
        ],
        style=padding_style
    )
    filter_label = toga.Label(text="Black frame filter configuration",style=padding_style)
    filter_section = toga.Box(
        children = [
            raw_output_switch := toga.Switch(id="option_luma_auto",text="Raw Output",on_change=toggle_child_widget_state,style=sep_style),
            luma_sample_label := toga.Label("Luma sample:"), luma_sample_input := NumberInput(id="option_luma_sample",value=300, min=0, style=short_sep_style),
            luma_base_label := toga.Label("Luma base:"), luma_base_input := NumberInput(id="option_luma_base",value=16, min=0, max=255, style=short_sep_style),
            luma_threshold_label := toga.Label("Luma threshold:"), luma_threshold_input := NumberInput(id="option_luma_threshold",value=16, min=0, max=255, style=short_sep_style)
        ],
        style = padding_style
    )

    control_section = toga.Box(
        children = [
            start_button := toga.Button("Start", on_press=start_handler, style=inline_style),
            stop_button := toga.Button("Stop", on_press=stop_handler, style=inline_style),
            stats_button := toga.Button("Stats", on_press=stats_handler, style=inline_style)
        ],
        style = padding_style
    )

    box = toga.Box(
        children=[
            vcam_label,
            vcam_section,
            toga.Divider(),
            filter_label,
            filter_section,
            toga.Divider(),
            control_section
            ],
        style = verticle_style
    )

    return box


if __name__ == "__main__":
    app = toga.App("Hello Camera", "dev.pufferoverflow.hellocamera", startup=build)
    app.main_loop()