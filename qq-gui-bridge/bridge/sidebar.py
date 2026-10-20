import re

import cv2

from bridge.ocr import normalize

TIME_SUFFIX = re.compile(r"(?:昨天|今天|前天|星期[一二三四五六日天])?\d{1,2}:\d{2}$")
DATE_SUFFIX = re.compile(r"\d{1,2}[/月]\d{1,2}日?$")
BARE_DAY = re.compile(r"(?:昨天|前天|星期[一二三四五六日天])$")
TRAILING_COUNT = re.compile(r"\s*\d{1,3}$")

MENTION_HINTS = ("有人@我", "@我", "有人@")
RED_RANGES = (
    ((0, 120, 110), (10, 255, 255)),
    ((170, 120, 110), (180, 255, 255)),
)


def clean_title(text: str) -> str:
    value = (text or "").strip()
    for pattern in (TIME_SUFFIX, DATE_SUFFIX, BARE_DAY):
        value = pattern.sub("", value)
    return value.strip()


def conversation_entries(rows, row_gap: int = 30):
    entries = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        if not entries or row["y"] - entries[-1]["y1"] > row_gap:
            entries.append({"y0": row["y"], "y1": row["y"], "rows": [row]})
        else:
            entries[-1]["rows"].append(row)
            entries[-1]["y1"] = row["y"]

    for entry in entries:
        entry["title"] = clean_title(entry["rows"][0]["text"])
        entry["name"] = entry["title"]
        entry["preview"] = " ".join(row["text"].strip() for row in entry["rows"][1:])
        entry["hint"] = any(hint in entry["preview"] for hint in MENTION_HINTS)
        entry["unread"] = entry["hint"]
        entry["badge"] = False
        entry["y"] = (entry["y0"] + entry["y1"]) / 2.0
    return [entry for entry in entries if entry["title"]]


def find_unread_badges(image, left_ratio: float = 0.5, min_area: int = 8):
    if image is None or getattr(image, "size", 0) == 0:
        return []
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.bitwise_or(
        cv2.inRange(hsv, RED_RANGES[0][0], RED_RANGES[0][1]),
        cv2.inRange(hsv, RED_RANGES[1][0], RED_RANGES[1][1]),
    )
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
    height, width = image.shape[:2]
    badges = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if area < min_area or w < 3 or h < 3:
            continue
        if x < width * left_ratio:
            continue
        if w > width * 0.4 or h > 40:
            continue
        badges.append({
            "x": float(centroids[index][0]),
            "y": float(centroids[index][1]),
            "w": int(w),
            "h": int(h),
        })
    return badges


def sidebar_entries(rows, badges, row_gap: int = 30, badge_tol: int = 26):
    entries = conversation_entries(rows, row_gap=row_gap)
    for badge in badges:
        best = None
        best_distance = None
        for entry in entries:
            if not (entry["y0"] - badge_tol <= badge["y"] <= entry["y1"] + badge_tol):
                continue
            distance = abs(entry["y"] - badge["y"])
            if best_distance is None or distance < best_distance:
                best = entry
                best_distance = distance
        if best is None:
            continue
        best["badge"] = True
        best["unread"] = True

    for entry in entries:
        if entry["badge"]:
            entry["preview"] = TRAILING_COUNT.sub("", entry["preview"]).strip()
    return entries


def unread_entries(entries, ignore=()):
    ignored = [normalize(item) for item in ignore if item]
    result = []
    for entry in entries:
        if not entry.get("unread"):
            continue
        title = normalize(entry.get("title", ""))
        if not title:
            continue
        if any(value in title for value in ignored):
            continue
        result.append(entry)
    return result
