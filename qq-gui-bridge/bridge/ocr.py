import re

import numpy as np
from rapidocr_onnxruntime import RapidOCR


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def is_timestamp(text: str) -> bool:
    value = normalize(text)
    return bool(re.fullmatch(r"(?:昨天|今天|前天|星期[一二三四五六日天])?\d{1,2}:\d{2}", value))


def is_level_label(text: str) -> bool:
    return normalize(text).lower().startswith("lv")


def group_rows(items, y_tol: int):
    rows = []
    for item in sorted(items, key=lambda value: (value["cy"], value["x0"])):
        placed = False
        for row in rows:
            if abs(row["cy"] - item["cy"]) <= y_tol:
                row["items"].append(item)
                row["cy"] = sum(value["cy"] for value in row["items"]) / len(row["items"])
                placed = True
                break
        if not placed:
            rows.append({"cy": item["cy"], "items": [item]})
    result = []
    for row in rows:
        parts = sorted(row["items"], key=lambda value: value["x0"])
        result.append({
            "y": round(row["cy"], 1),
            "x0": min(part["x0"] for part in parts),
            "x1": max(part["x1"] for part in parts),
            "text": "".join(part["text"] for part in parts),
        })
    result.sort(key=lambda value: value["y"])
    return result


class OcrEngine:
    def __init__(self, min_score: float = 0.5, y_tol: int = 7):
        self.engine = RapidOCR()
        self.min_score = min_score
        self.y_tol = y_tol

    def read(self, image) -> list:
        result, _ = self.engine(np.asarray(image))
        items = []
        for box, text, score in result or []:
            value = float(score)
            if value < self.min_score:
                continue
            points = np.array(box, dtype=np.float32)
            items.append({
                "text": text,
                "score": value,
                "x0": float(points[:, 0].min()),
                "x1": float(points[:, 0].max()),
                "cy": float((points[:, 1].min() + points[:, 1].max()) / 2),
            })
        return group_rows(items, self.y_tol)


def is_noise_text(text: str) -> bool:
    value = normalize(text)
    if len(value) < 2:
        return True
    if "�" in value or "□" in value:
        return True
    concrete = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value)
    if len(concrete) < 2:
        return True
    return len(concrete) < len(value) * 0.34


def clean_sender_name(label: str) -> str:
    value = (label or "").strip()
    value = re.sub(r"^LV\d+\s*", "", value, flags=re.I)
    value = re.sub(r"^殿堂\s*", "", value)
    value = value.strip()
    if not value or value.lower().startswith("lv"):
        return "unknown"
    return value


def find_sender(rows, index: int) -> str:
    for row in reversed(rows[max(0, index - 4):index]):
        text = row["text"].strip()
        if is_level_label(text) and not is_timestamp(text):
            return clean_sender_name(text)
    return "unknown"


def is_self_row(row, chat_width: int, self_ratio: float = 0.8, image=None) -> bool:
    colored = row_self_by_color(row, image)
    if colored:
        return True
    right = row.get("x1", row.get("x0", 0) + 1)
    if right > chat_width * 0.9:
        return True
    if colored is False:
        return False
    return right > chat_width * self_ratio


def row_self_by_color(row, image, min_ratio: float = 0.25, pad: int = 12):
    if image is None or getattr(image, "size", 0) == 0:
        return None
    y = int(row.get("y", 0))
    x0 = int(row.get("x0", 0))
    x1 = int(row.get("x1", x0 + 1))
    top = max(0, y - pad)
    bottom = min(image.shape[0], y + pad + 1)
    left = max(0, x0 - 6)
    right = min(image.shape[1], x1 + 6)
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        return None
    blue = crop[:, :, 0].astype("int16")
    green = crop[:, :, 1].astype("int16")
    red = crop[:, :, 2].astype("int16")
    mask = (blue > red + 25) & (blue > 170) & (green > red)
    return bool(mask.mean() >= min_ratio)


def parse_messages(rows, chat_width: int, self_ratio: float = 0.8, image=None):
    messages = []
    current_sender = "unknown"
    current_self = False
    for row in rows:
        text = row["text"].strip()
        if not text or is_timestamp(text):
            continue
        if is_level_label(text):
            current_sender = clean_sender_name(text)
            current_self = is_self_row(row, chat_width, self_ratio, image)
            continue
        if re.fullmatch(r"\+\d+", normalize(text)):
            continue
        messages.append({
            "sender": current_sender,
            "self": current_self or is_self_row(row, chat_width, self_ratio, image),
            "text": text,
            "x0": row["x0"],
            "y": row["y"],
        })
    return messages
