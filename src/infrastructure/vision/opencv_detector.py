"""OpenCV-based object detector.

Produces application-layer DetectionBoxDTOs from a video frame.
Translates raw OpenCV/DNN output into the contracts the application
layer understands. Contains no business rules (no threat scoring here).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.application.dtos.detection_dtos import DetectionBoxDTO


@dataclass
class OpenCVDetectorConfig:
    model_path: str
    config_path: str
    class_names: list[str]
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.4


class OpenCVDetector:
    """Thin wrapper around an OpenCV DNN model (e.g. YOLO / MobileNet-SSD)."""

    def __init__(self, config: OpenCVDetectorConfig) -> None:
        self._config = config
        self._net = cv2.dnn.readNet(config.model_path, config.config_path)

    def detect(self, frame: "np.ndarray") -> list[DetectionBoxDTO]:
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame, scalefactor=1 / 255.0, size=(416, 416), swapRB=True, crop=False
        )
        self._net.setInput(blob)
        raw_outputs = self._net.forward(self._output_layers())

        boxes: list[list[float]] = []
        confidences: list[float] = []
        class_ids: list[int] = []

        for output in raw_outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                if confidence < self._config.confidence_threshold:
                    continue
                cx, cy, w, h = detection[0:4]
                x = (cx - w / 2)
                y = (cy - h / 2)
                boxes.append([float(x), float(y), float(w), float(h)])
                confidences.append(confidence)
                class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(
            boxes,
            confidences,
            self._config.confidence_threshold,
            self._config.nms_threshold,
        )

        results: list[DetectionBoxDTO] = []
        for i in np.array(indices).flatten() if len(indices) else []:
            x, y, w, h = boxes[i]
            label = self._label_for(class_ids[i])
            results.append(
                DetectionBoxDTO(
                    label=label,
                    confidence=confidences[i],
                    x=_clamp(x),
                    y=_clamp(y),
                    width=_clamp(w, minimum=1e-6),
                    height=_clamp(h, minimum=1e-6),
                )
            )
        return results

    def _output_layers(self) -> list[str]:
        layer_names = self._net.getLayerNames()
        return [
            layer_names[i - 1]
            for i in np.array(self._net.getUnconnectedOutLayers()).flatten()
        ]

    def _label_for(self, class_id: int) -> str:
        if 0 <= class_id < len(self._config.class_names):
            return self._config.class_names[class_id]
        return "object"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
