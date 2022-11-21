import json
import os
import threading
import time
from typing import Any

import cv2
import numpy as np
import pyboof as pb
import websocket
from websocket import WebSocket, create_connection

from drone.config import DRONE_ID, FILENAME, VIDEO_URL
from drone.utils import make_logger, read_qrcode

from dotenv import load_dotenv

env_path = "/home/pi/drone/.env.drone"
load_dotenv(env_path)

logger_ = make_logger()

try:
    detector = pb.FactoryFiducial(np.uint8).qrcode()
except:
    logger_.error("Erro na geração de detector pyboof")
    time.sleep(120)
    exit(1)

state: dict[str, Any] = {
    "capture_qrcode": False,
    "connected": False,
    "transmission_on": False,
    "video_capture": None
}

VIDEO_URL = 0
state["video_capture"] = cv2.VideoCapture(VIDEO_URL)

def frame_reader() -> None:

    global state
    state["transmission_on"] = True

    while True:
        ret = state["video_capture"].grab()
        if not ret:
            state["transmission_on"] = False

def message_exchanges(ws: WebSocket):

    global state

    ws.send(str(DRONE_ID))

    while True:

        try:
            request_id: str = ws.recv()

            if not state["transmission_on"]:
                logger_.info("Frames da câmera não estão disponíveis...")
                continue

            ret, frame = state["video_capture"].read()
            print(ret)
            if not ret:
                continue

            lectures: dict = read_qrcode(detector, logger_, FILENAME, frame, request_id)
            logger_.info("Lectures: {}".format(lectures))

            ws.send(json.dumps(lectures))

        except:
            state["connected"] = False
            return


state["connected"] = True

while state["connected"]:

    websocket.enableTrace(True)
    ws: WebSocket = create_connection("ws://{}:{}/capture/ws".format(
        os.getenv("MANAGER_HOST"), os.getenv("MANAGER_PORT")
    ))

    frame_t = threading.Thread(target=frame_reader)
    frame_ex = threading.Thread(target=message_exchanges, args=(ws,))

    frame_t.start()
    frame_ex.start()

    while True:
        time.sleep(0.1)
        if not state["transmission_on"]:
            state["video_capture"] = cv2.VideoCapture(VIDEO_URL)
            frame_t.start()
