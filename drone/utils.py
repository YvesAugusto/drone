import time
from logging import DEBUG, FileHandler, Formatter, Logger, getLogger

import cv2
import numpy as np
import pyboof as pb


def make_logger():

    logger_: Logger = getLogger('doca')
    logger_.setLevel(DEBUG)

    fh = FileHandler('doca.log')
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
        "lectures": messages
    }
    return messages
