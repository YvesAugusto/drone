import json
import os
import threading
import time
from typing import Any

import cv2
import numpy as np
import pyboof as pb
from dotenv import load_dotenv

from drone.config import ENV_PATH, FILENAME

load_dotenv(ENV_PATH)

from websocket import WebSocket

from drone.utils import (ask_info_to_manager, check_log_last_line_camera,
                         get_websocket_connection, make_logger, read_qrcode)

DRONE_ID = os.getenv("DRONE_ID")

logger_ = make_logger()

def frame_reader() -> None:

    global state
    state["transmission_on"] = True

    while True:
        ret = state["video_capture"].grab()
        if not ret:
            state["transmission_on"] = False
            return

def message_exchanges(ws: WebSocket):

    global state

    ws.send(str(DRONE_ID))

    while True:

        try:
            request_id: str = ws.recv()

            if request_id == "connection_test":
                continue

            payload = {
                "message": None,
                "error": True
            }

            if not state["transmission_on"]:
                payload["message"] = "Frames da câmera não estão disponíveis..."
                ws.send(json.dumps(payload))
                continue

            ret, frame = state["video_capture"].read()
            if not ret:
                payload["message"] = "Frames da câmera não estão disponíveis..."
                state["transmission_on"] = False
                ws.send(json.dumps(payload))
                continue

            lectures: dict = read_qrcode(detector, logger_, FILENAME, frame, request_id)
            logger_.info("Lectures: {}".format(lectures))

            ws.send(json.dumps(lectures))

        except:
            state["connected"] = False
            return

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

REQUEST_URL = "http://{}:{}/subscribe/get/{}".format(
    os.getenv("MANAGER_HOST"), os.getenv("MANAGER_PORT"), os.getenv("DRONE_ID")
)

response = ask_info_to_manager(logger_, REQUEST_URL)
logger_.info("Endpoint response: {}".format(response))
try:
    VIDEO_URL = response["data"]["camera_uri"]
except:
    logger_.error("Missing key on endpoint response...")
    exit(1)

if VIDEO_URL == "0":
    VIDEO_URL = 0

logger_.info("Trying to connect to camera: {}".format(VIDEO_URL))
while True:

    try:
        state["video_capture"] = cv2.VideoCapture(VIDEO_URL)
    except:
        last_line_is_error = check_log_last_line_camera(logger_)
        time.sleep(10)
        continue

    ret, frame = state["video_capture"].read()
    if not ret:
        check_log_last_line_camera(logger_, VIDEO_URL)
        time.sleep(10)
        continue

    break

logger_.info("Successfully connected to camera {}".format(VIDEO_URL))
frame_t = threading.Thread(target=frame_reader)
frame_t.start()

while True:

    ws: WebSocket = get_websocket_connection(logger_)
    state["connected"] = True
    frame_ex = threading.Thread(target=message_exchanges, args=(ws,))

    frame_ex.start()

    while state["connected"]:
        time.sleep(0.1)
        if not state["transmission_on"]:
            state["video_capture"].release()
            state["video_capture"] = cv2.VideoCapture(VIDEO_URL)
            frame_t = threading.Thread(target=frame_reader)
            frame_t.start()
