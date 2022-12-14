import errno
import os
import time
from logging import DEBUG, FileHandler, Formatter, Logger, getLogger
from socket import error
from typing import Any

import cv2
import numpy as np
import pyboof as pb
import regex as re
import requests
from websocket import WebSocket, create_connection

LOG_PATH = os.getenv("LOG_PATH")

CAMERA_ERROR_REPLACE = "[{}] Could not connect to camera. Tried {} time(s)"
camera_error_matcher = re.compile(".*Could not connect to camera. Tried (?P<tries>\d+) time\(s\)$")

ASK_INFO_ERROR_REPLACE = "Endpoint {} request has failed. Tried {} time(s)"
ask_info_matcher = re.compile(".*request has failed. Tried (?P<tries>\d+) time\(s\)$")

WEBSOCKET_REFUSED_REPLACE = "Websocket {} connection refused. Tried {} time(s)"
websocket_refused_matcher = re.compile(".*connection refused. Tried (?P<tries>\d+) time\(s\)$")

def make_logger():

    logger_: Logger = getLogger('drone')
    logger_.setLevel(DEBUG)

    fh = FileHandler('drone.log')
    fh.setLevel(DEBUG)

    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    logger_.addHandler(fh)

    return logger_

def read_qrcode(detector, logger_, FILENAME, frame, request_id):

    response = {"message": None, "request_id": request_id}
    logger_.info("Efetuando captura...")

    shape = frame.shape
    logger_.info("Shape da imagem: {}".format(shape))

    try:
        cv2.imwrite(FILENAME, frame)
    except:
        response["message"] = "Não foi possível escrever a imagem"
        logger_.error("[{}] Não foi possível escrever a imagem".format(request_id))
        return
    try:
        image = pb.load_single_band(FILENAME, np.uint8)
    except:
        response["message"] = "Não foi possível ler a imagem"
        logger_.error("[{}] Não foi possível ler a imagem".format(request_id))
        return

    messages: list = []

    try:
        start_timestamp = time.time()
        detector.detect(image)
        delta = time.time() - start_timestamp
        logger_.info("Capture took {}s".format(delta))
    except:
        response["message"] = "Não foi possível aplicar a detecção"
        logger_.error("[{}] Não foi possível aplicar a detecção".format(request_id))
        return
    
    for qr in detector.detections:
        messages.append(
            {
                "content": qr.message,
                "bounds": list(map(lambda v: (v.x, v.y), qr.bounds.vertexes))
            }
        )

    try:
        cv2.imwrite(FILENAME, frame)
    except:
        response["message"] = "Não foi possível escrever a imagem"
        logger_.error("[{}] Não foi possível escrever a imagem".format(request_id))
        return

    messages = {
        "request_id": request_id,
        "shape": shape[:2],
        "message": "Sucesso",
        "lectures": messages,
        "error": False
    }
    return messages

def read_log_lines():

    lines: list[str] = open('drone.log', 'r').readlines()

    return lines

def check_log_last_line(
    logger: Logger, 
    request_string: str,
    matcher: Any,
    replace_string: str
):

    lines: list[str] = read_log_lines()

    last_line: str = lines[-1]

    MATCH = matcher.match(last_line)
    if MATCH is None:
        WRITE_MESSAGE = replace_string.format(request_string, 1)
        logger.error(WRITE_MESSAGE)
        return

    tries = MATCH.groupdict()["tries"]
    REPLACE_MESSAGE = replace_string.format(request_string, int(tries) + 1)

    lines = lines[:-1]

    open(LOG_PATH, 'w').writelines(lines)
    logger.error(REPLACE_MESSAGE)

    return

def check_log_last_line_camera(logger, request_string):

    check_log_last_line(
        logger, request_string, 
        camera_error_matcher, 
        CAMERA_ERROR_REPLACE
    )

    

def ask_info_to_manager(logger, request_string):

    while True:

        try:
            response = requests.get(request_string, timeout=5).json()

        except:
            check_log_last_line(
                logger, request_string, 
                ask_info_matcher, 
                ASK_INFO_ERROR_REPLACE
            )
            time.sleep(5)
            continue

        break

    return response

def get_websocket_connection(
    logger: Logger
):

    while True:

        try:
            ws_string = "ws://{}:{}/capture/ws".format(
            os.getenv("MANAGER_HOST"), os.getenv("MANAGER_PORT")
            )
            ws: WebSocket = create_connection(ws_string)
            
        except error as err:
            if err.errno == errno.ECONNREFUSED:
                check_log_last_line(
                    logger, ws_string, 
                    websocket_refused_matcher, 
                    WEBSOCKET_REFUSED_REPLACE
                )
            time.sleep(5)
            continue

        break
    
    return ws
