import asyncio
import io
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import cv2
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = Path(os.getenv("DRIDHA_MODEL_PATH", str(BASE_DIR / "best.pt"))).expanduser()
WAYPOINTS_FILE = Path(os.getenv("DRIDHA_WAYPOINTS_FILE", str(BASE_DIR / "Dridha_Mission.waypoints"))).expanduser()
CACHE_DIR = BASE_DIR / "cache"
ORIGINALS_DIR = CACHE_DIR / "originals"
ANNOTATED_DIR = CACHE_DIR / "annotated"

DRIVE_ROOT_FOLDER_ID = os.getenv("DRIDHA_DRIVE_ROOT_FOLDER_ID", "").strip()
POLL_INTERVAL_SECONDS = float(os.getenv("DRIDHA_POLL_INTERVAL_SECONDS", "4"))
CONFIDENCE = float(os.getenv("DRIDHA_CONFIDENCE", "0.50"))
MIN_GREEN_RATIO = float(os.getenv("DRIDHA_MIN_GREEN_RATIO", "0.18"))
MIN_EXG_RATIO = float(os.getenv("DRIDHA_MIN_EXG_RATIO", "0.12"))
MIN_MEAN_SATURATION = float(os.getenv("DRIDHA_MIN_MEAN_SATURATION", "45"))

allowed_origins = [
    origin.strip()
    for origin in os.getenv("DRIDHA_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
if not allowed_origins:
    allowed_origins = ["*"]

app = FastAPI(title="Dridha Weed Detection API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = None
drive_service = None
log_clients = []
log_history = deque(maxlen=300)
detections = []
synced_images = []
processed_file_ids = set()
seen_session_ids = set()
session_metadata_cache = {}
is_monitoring = False
waypoint_seq = 1
main_loop = {"loop": None}
poller_ref = {"thread": None, "stop": None}


def ts():
    return datetime.now().strftime("%H:%M:%S")


def file_id_path(folder: Path, file_id: str, suffix: str):
    folder.mkdir(parents=True, exist_ok=True)
    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return folder / f"{file_id}{safe_suffix}"


def get_service_account_info():
    raw_json = os.getenv("DRIDHA_GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    file_path = os.getenv("DRIDHA_GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()

    if raw_json:
        return json.loads(raw_json)
    if file_path:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return None


def load_drive_service():
    global drive_service

    info = get_service_account_info()
    if not info:
        drive_service = None
        return False

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return True


def load_model():
    global model
    if not MODEL_PATH.exists():
        model = None
        return False

    original_torch_load = torch.load

    def trusted_torch_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    with patch("torch.load", trusted_torch_load):
        model = YOLO(str(MODEL_PATH))
    return True


async def broadcast(msg: str, level: str = "info"):
    payload = {"time": ts(), "msg": msg, "level": level}
    log_history.append(payload)

    dead = []
    text = json.dumps(payload)
    for ws in log_clients:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)

    for ws in dead:
        if ws in log_clients:
            log_clients.remove(ws)


def sync_broadcast(msg: str, level: str = "info"):
    loop = main_loop["loop"]
    if not loop:
        return
    try:
        asyncio.run_coroutine_threadsafe(broadcast(msg, level), loop)
    except Exception:
        pass


def reset_runtime_state(preserve_drive_seen: bool = False):
    global waypoint_seq, is_monitoring

    detections.clear()
    synced_images.clear()
    log_history.clear()
    session_metadata_cache.clear()
    waypoint_seq = 1
    is_monitoring = False

    if not preserve_drive_seen:
        processed_file_ids.clear()
        seen_session_ids.clear()

    if WAYPOINTS_FILE.exists():
        WAYPOINTS_FILE.unlink()

    for folder in [ORIGINALS_DIR, ANNOTATED_DIR]:
        if folder.exists():
            for item in folder.glob("*"):
                if item.is_file():
                    item.unlink()


def list_drive_children(folder_id: str, mime_type: str | None = None):
    if not drive_service or not folder_id:
        return []

    query_parts = [f"'{folder_id}' in parents", "trashed = false"]
    if mime_type:
        query_parts.append(f"mimeType = '{mime_type}'")
    query = " and ".join(query_parts)

    files = []
    page_token = None
    while True:
        response = (
            drive_service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime)",
                orderBy="modifiedTime desc",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return files


def download_drive_file(file_id: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(destination, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return destination


def parse_metadata_file(content: str):
    mapping = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("IMAGE_NAME"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 5:
            continue
        mapping[parts[0]] = {
            "lat": parts[1],
            "lon": parts[2],
            "alt": parts[3],
            "date_time": parts[4],
        }
    return mapping


def get_session_metadata(session_id: str, image_name: str):
    cache = session_metadata_cache.get(session_id)
    if cache and image_name in cache["mapping"]:
        return cache["mapping"][image_name]

    text_files = [
        item
        for item in list_drive_children(session_id)
        if item["name"].startswith("FlightLog") and item["name"].lower().endswith(".txt")
    ]
    if not text_files:
        return None

    latest = text_files[0]
    local_path = file_id_path(CACHE_DIR / "logs", latest["id"], ".txt")
    download_drive_file(latest["id"], local_path)
    mapping = parse_metadata_file(local_path.read_text(encoding="utf-8", errors="ignore"))
    session_metadata_cache[session_id] = {"file_id": latest["id"], "mapping": mapping}
    return mapping.get(image_name)


def append_waypoints(metadata: dict):
    global waypoint_seq

    WAYPOINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not WAYPOINTS_FILE.exists() or WAYPOINTS_FILE.stat().st_size == 0
    with WAYPOINTS_FILE.open("a", encoding="utf-8") as handle:
        if write_header:
            handle.write("QGC WPL 110\n")
        handle.write(
            f"{waypoint_seq}\t0\t3\t16\t0\t0\t0\t0\t{metadata['lat']}\t{metadata['lon']}\t{metadata['alt']}\t1\n"
        )
        handle.write(f"{waypoint_seq + 1}\t0\t3\t183\t9\t1500\t0\t0\t0\t0\t0\t1\n")
    waypoint_seq += 2


def filter_valid_boxes(img_path: Path, result):
    image = cv2.imread(str(img_path))
    if image is None:
        return []

    image_h, image_w = image.shape[:2]
    total_area = max(1, image_h * image_w)
    boxes = result.boxes
    if boxes is None or len(boxes) <= 0:
        return []

    valid = []
    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()

    for coords, confidence in zip(xyxy, confs):
        x1, y1, x2, y2 = [int(v) for v in coords]
        x1 = max(0, min(x1, image_w - 1))
        x2 = max(0, min(x2, image_w))
        y1 = max(0, min(y1, image_h - 1))
        y2 = max(0, min(y2, image_h))
        if x2 <= x1 or y2 <= y1:
            continue

        box_w = x2 - x1
        box_h = y2 - y1
        area_ratio = (box_w * box_h) / total_area
        aspect_ratio = box_w / max(1, box_h)

        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv, (28, 35, 30), (95, 255, 255))
        green_ratio = float(cv2.countNonZero(green_mask)) / max(1, crop.shape[0] * crop.shape[1])
        mean_saturation = float(hsv[:, :, 1].mean())

        b, g, r = cv2.split(crop.astype("float32"))
        exg = (2 * g) - r - b
        exg_ratio = float((exg > 20).sum()) / max(1, crop.shape[0] * crop.shape[1])
        green_dominant_ratio = float(((g > r + 8) & (g > b + 8)).sum()) / max(1, crop.shape[0] * crop.shape[1])

        if area_ratio < 0.01 or area_ratio > 0.55:
            continue
        if aspect_ratio > 2.8 or aspect_ratio < 0.18:
            continue
        if green_ratio < MIN_GREEN_RATIO:
            continue
        if exg_ratio < MIN_EXG_RATIO:
            continue
        if green_dominant_ratio < MIN_GREEN_RATIO:
            continue
        if mean_saturation < MIN_MEAN_SATURATION:
            continue

        valid.append(
            {
                "xyxy": (x1, y1, x2, y2),
                "confidence": float(confidence),
            }
        )

    return valid


def save_annotated_result(img_path: Path, file_id: str, valid_boxes: list[dict]):
    annotated_path = file_id_path(ANNOTATED_DIR, file_id, ".jpg")
    image = cv2.imread(str(img_path))
    if image is None:
        return annotated_path

    for item in valid_boxes:
        x1, y1, x2, y2 = item["xyxy"]
        conf = item["confidence"]
        cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
        cv2.putText(
            image,
            f"weed {conf:.2f}",
            (x1, max(24, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(annotated_path), image)
    return annotated_path


def is_image_file(item: dict):
    mime_type = item.get("mimeType", "")
    name = item.get("name", "").lower()
    return mime_type.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png"))


def process_drive_image(session: dict, image_file: dict):
    image_id = image_file["id"]
    if image_id in processed_file_ids:
        return

    processed_file_ids.add(image_id)
    img_name = image_file["name"]
    suffix = Path(img_name).suffix or ".jpg"
    original_path = file_id_path(ORIGINALS_DIR, image_id, suffix)
    download_drive_file(image_id, original_path)

    synced_images.append({"id": len(synced_images) + 1, "file_id": image_id, "name": img_name, "path": str(original_path), "time": ts()})
    sync_broadcast(f"[SYNC] {img_name} received from Google Drive", "sync")

    metadata = get_session_metadata(session["id"], img_name)
    if not metadata:
        sync_broadcast(f"[SKIP] No metadata found for {img_name}", "warn")
        return

    if model is None:
        sync_broadcast("[ERROR] YOLO model not loaded", "error")
        return

    try:
        results = model.predict(source=str(original_path), conf=CONFIDENCE, verbose=False)
    except Exception as exc:
        sync_broadcast(f"[ERROR] Prediction failed for {img_name}: {exc}", "error")
        return

    result = results[0]
    valid_boxes = filter_valid_boxes(original_path, result)
    if not valid_boxes:
        sync_broadcast(f"[CLEAR] No weeds in {img_name}", "clear")
        return

    annotated_path = save_annotated_result(original_path, image_id, valid_boxes)
    append_waypoints(metadata)
    detections.append(
        {
            "id": len(detections) + 1,
            "name": img_name,
            "file_id": image_id,
            "path": str(original_path),
            "annotated_path": str(annotated_path),
            "lat": metadata["lat"],
            "lon": metadata["lon"],
            "alt": metadata["alt"],
            "count": len(valid_boxes),
            "time": ts(),
            "confidence": max(item["confidence"] for item in valid_boxes),
        }
    )
    sync_broadcast(f"[WEED] {len(valid_boxes)} weed(s) at {metadata['lat']}, {metadata['lon']} - waypoint saved", "weed")


def snapshot_existing_drive_files():
    if not DRIVE_ROOT_FOLDER_ID or not drive_service:
        return

    session_folders = list_drive_children(DRIVE_ROOT_FOLDER_ID, "application/vnd.google-apps.folder")
    for session in session_folders:
        seen_session_ids.add(session["id"])
        for item in list_drive_children(session["id"]):
            if is_image_file(item):
                processed_file_ids.add(item["id"])


def poll_drive():
    stop_event = threading.Event()
    poller_ref["stop"] = stop_event

    def loop():
        while not stop_event.is_set():
            try:
                if drive_service and DRIVE_ROOT_FOLDER_ID:
                    sessions = list_drive_children(DRIVE_ROOT_FOLDER_ID, "application/vnd.google-apps.folder")
                    for session in sessions:
                        for item in list_drive_children(session["id"]):
                            if is_image_file(item):
                                process_drive_image(session, item)
            except Exception as exc:
                sync_broadcast(f"[WARN] Drive polling error: {exc}", "warn")

            stop_event.wait(POLL_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, name="dridha-drive-poller", daemon=True)
    thread.start()
    poller_ref["thread"] = thread


@app.on_event("startup")
async def startup():
    global is_monitoring

    main_loop["loop"] = asyncio.get_running_loop()
    reset_runtime_state()
    await broadcast("[SYSTEM] Dridha backend started", "system")
    await broadcast("[SYSTEM] Cleared previous session data", "system")

    if load_model():
        await broadcast(f"[SYSTEM] YOLO model loaded from {MODEL_PATH.name}", "system")
    else:
        await broadcast(f"[WARN] Model file not found at {MODEL_PATH}", "warn")

    if load_drive_service() and DRIVE_ROOT_FOLDER_ID:
        snapshot_existing_drive_files()
        poll_drive()
        is_monitoring = True
        await broadcast("[SYSTEM] Monitoring Google Drive root folder", "system")
    else:
        await broadcast("[WARN] Google Drive credentials or folder id missing", "warn")


@app.on_event("shutdown")
def shutdown():
    if poller_ref["stop"]:
        poller_ref["stop"].set()
    if poller_ref["thread"] and poller_ref["thread"].is_alive():
        poller_ref["thread"].join(timeout=2)


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    log_clients.append(websocket)

    for item in list(log_history)[-50:]:
        await websocket.send_text(json.dumps(item))

    await websocket.send_text(
        json.dumps(
            {
                "time": ts(),
                "msg": f"[SYSTEM] Connected - {len(detections)} detection(s) so far",
                "level": "system",
            }
        )
    )

    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"time": ts(), "msg": "ping", "level": "ping"}))
    except (WebSocketDisconnect, Exception):
        if websocket in log_clients:
            log_clients.remove(websocket)


@app.get("/api/health")
def health():
    return {"ok": True, "time": ts()}


@app.get("/api/status")
def status():
    return {
        "monitoring": is_monitoring,
        "model_loaded": model is not None,
        "detections": len(detections),
        "synced_images": len(synced_images),
        "waypoints_ready": WAYPOINTS_FILE.exists(),
        "watch_path": DRIVE_ROOT_FOLDER_ID,
        "model_path": str(MODEL_PATH),
        "last_event": log_history[-1] if log_history else None,
    }


@app.get("/api/detections")
def get_detections():
    return detections


@app.get("/api/synced")
def get_synced():
    return synced_images[-100:]


@app.get("/api/waypoints/download")
def download_waypoints():
    if WAYPOINTS_FILE.exists():
        return FileResponse(str(WAYPOINTS_FILE), filename="Dridha_Mission.waypoints", media_type="application/octet-stream")
    return JSONResponse({"error": "No waypoints file yet"}, status_code=404)


@app.get("/api/waypoints/preview")
def preview_waypoints():
    if not WAYPOINTS_FILE.exists():
        return {"content": ""}
    with WAYPOINTS_FILE.open("r", encoding="utf-8", errors="ignore") as handle:
        return {"content": handle.read()}


@app.get("/api/detections/{detection_id}/image")
def serve_detection_image(detection_id: int):
    for item in detections:
        if item["id"] == detection_id:
            path = Path(item["annotated_path"])
            if path.exists():
                return FileResponse(str(path))
    return JSONResponse({"error": "Detection image not found"}, status_code=404)


@app.get("/api/synced/{sync_id}/image")
def serve_synced_image(sync_id: int):
    for item in synced_images:
        if item["id"] == sync_id:
            path = Path(item["path"])
            if path.exists():
                return FileResponse(str(path))
    return JSONResponse({"error": "Synced image not found"}, status_code=404)


@app.delete("/api/session/reset")
async def reset_session():
    reset_runtime_state(preserve_drive_seen=True)
    await broadcast("[SYSTEM] Session reset", "system")
    return {"ok": True}
