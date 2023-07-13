from asyncio import Task
import os
import json
import os.path
from threading import Thread

import pibooth
from pibooth.utils import LOGGER, PoolingTimer
from collections import deque
import glob

from PIL import Image

__version__ = "2023.05.26"

SECTION = 'ROLLPHOTO'
layout_timer = PoolingTimer(4)
FIRST=True

@pibooth.hookimpl
def pibooth_configure(cfg):
    """Declare the new configuration options"""
    cfg.add_option(SECTION, 'is_rolling_photo', False,
                   "Enable rolling photo at the end")
    cfg.add_option(SECTION, 'pausing_time', '5',
                   "Pause beteween tow photo if plugin is enabled")
    
    cfg.add_option(SECTION, 'timeout_last_photo', '5',
                   "timeout to show the last photo took before rolling")

@pibooth.hookimpl
def pibooth_startup(app, cfg):
    LOGGER.debug("Into startup rolling photo to configure local properties")
    directory = cfg.get('GENERAL', 'directory')
    app.roll_photo = RollPhoto(directory)
    thread_to_load = Thread(target=app.roll_photo.task_to_load)
    thread_to_load.start()

@pibooth.hookimpl
def state_wait_enter(cfg, app):
    is_rolling_photo = cfg.getboolean(SECTION, 'is_rolling_photo')
    LOGGER.debug(f'nb_taken {app.current_taken}')
    if is_rolling_photo and app.current_taken > 0:
        timeout_last_photo = cfg.getint(SECTION, 'timeout_last_photo')
        layout_timer.timeout = timeout_last_photo
        layout_timer.start()

@pibooth.hookimpl
def state_wait_do(cfg, app, win, events): 
    is_rolling_photo = cfg.getboolean(SECTION, 'is_rolling_photo')
    if is_rolling_photo and layout_timer.is_timeout() and app.current_taken > 0:
        #   LOGGER.debug('Enter into rolling core')
        pausing_time = cfg.getint(SECTION, 'pausing_time')
        layout_timer.timeout = pausing_time
        layout_timer.start()
        image_to_show = app.roll_photo.get_last_pil_image()
        if image_to_show is not None:
            #image = Image.open(image_to_show)
            win.show_intro(image_to_show, app.printer.is_ready()
                           and app.count.remaining_duplicates > 0)
            #image.close()

class RollPhoto(object):
    def __init__(self, path_file_saved):
        self.set_path = set()
        self.queue_path = deque([])
        self.queue_PIL = deque([])
        self.load_file_path_saved(path_file_saved)
        self.directory = path_file_saved

    def load_file_path_saved(self, path_file_saved):
        #LOGGER.debug(path_file_saved)
        pattern_jpg = f'{path_file_saved}/*.jpg'
        
        res = glob.glob(pattern_jpg)
        for file in res:
            if not file in self.set_path:
                self.set_path.add(file)
                self.queue_path.append(file)
        #LOGGER.debug(self.queue_path)

    def get_last_to_show(self):
        if len(self.queue_path) == 0:
            return None
        
        last_to_show = self.queue_path.popleft()
        self.queue_path.append(last_to_show)
        return last_to_show
    
    def get_last_pil_image(self):
        if self.queue_PIL is not None and len(self.queue_PIL) > 0:
            last_pil = self.queue_PIL.popleft()

            thread_to_load = Thread(target=self.task_to_load)
            thread_to_load.start()
            return last_pil
        elif self.queue_PIL is not None and len(self.queue_PIL) == 0:
            thread_to_load = Thread(target=self.task_to_load)
            thread_to_load.start()

    # a custom function that blocks for a moment
    def task_to_load(self):
        #LOGGER.debug('New thread loader photo')
        self.load_file_path_saved(self.directory)
        # display a message
        while len(self.queue_PIL) < 10:
            #LOGGER.debug(f'Loading {len(self.queue_PIL)} on 10')
            image = Image.open(self.get_last_to_show())
            self.queue_PIL.append(image)
        