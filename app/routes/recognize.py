"""
Face Recognition Routes — powered by InsightFace (RetinaFace + ArcFace)
=======================================================================
SOTA face detection & recognition that works reliably across all skin tones.

Endpoints:
    POST /recognize       — single image face recognition
    POST /recognize-video — video file face recognition (multi-frame)
"""

import asyncio
import io
import logging
import os
import traceback
import uuid
import base64
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.user import User
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.meeting import Meeting
from app.models.organization import Admin, Organization
from app.auth import get_current_admin
from app.face_engine import (
    get_engine,
    decode_embedding,
    encode_embedding,
    MEMBER_MATCH_THRESHOLD,
    VISITOR_MATCH_THRESHOLD,
    SAME_FACE_THRESHOLD,
    VIDEO_SAME_FACE_THRESHOLD,
)
from app.services.sms_service import is_sms_configured, send_attendance_sms

router = APIRouter(tags=["Recognition"])

UNKNOWN_FACES_DIR = Path("app/static/unknown_faces")
UNKNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)

# Maximum dimension for face detection (resize if larger)
MAX_DIMENSION = 1600
# Minimum dimension (upscale if smaller for better detection)
MIN_FACE_SIZE = 80

# Check if ffmpeg is available for video conversion
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _decode_any_image(image_data: bytes) -> np.ndarray | None:
    """Decode image bytes from ANY format to a BGR numpy array.
    Tries cv2 first, then falls back to PIL (handles HEIC, HEIF, AVIF, WebP,
    TIFF, RAW, etc.).  If ffmpeg is available, uses it as a last resort for
    truly exotic formats."""
    # 1. Try cv2 (JPEG, PNG, BMP, WebP, TIFF, most common formats)
    nparr = np.frombuffer(image_data, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if bgr is not None:
        return bgr

    # 2. Try PIL (handles HEIC via pillow-heif, AVIF, WebP, etc.)
    try:
        pil_img = Image.open(io.BytesIO(image_data))
        pil_img = pil_img.convert("RGB")
        rgb = np.array(pil_img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        pass

    # 3. Last resort — convert with ffmpeg if available
    if HAS_FFMPEG:
        try:
            with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp_in:
                tmp_in.write(image_data)
                tmp_in_path = tmp_in.name
            tmp_out_path = tmp_in_path + ".png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_in_path, "-frames:v", "1", tmp_out_path],
                capture_output=True, timeout=15,
            )
            if os.path.exists(tmp_out_path):
                bgr = cv2.imread(tmp_out_path)
                os.unlink(tmp_out_path)
            os.unlink(tmp_in_path)
            if bgr is not None:
                return bgr
        except Exception:
            pass

    return None


def _extract_video_frames(video_data: bytes, max_frames: int = 16) -> list[np.ndarray]:
    """Extract frames from any video format and any size.
    Uses cv2 first, ffmpeg direct frame extraction as fallback,
    then ffmpeg full conversion as last resort.
    Returns list of BGR numpy arrays."""
    frames = []

    # Detect file signature for better temp extension
    ext = ".mp4"
    if video_data[:4] == b'\x1a\x45\xdf\xa3':
        ext = ".mkv"
    elif video_data[:4] == b'RIFF':
        ext = ".avi"
    elif video_data[:3] == b'FLV':
        ext = ".flv"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(video_data)
        tmp_path = tmp.name

    try:
        # Try cv2 VideoCapture first
        cap = cv2.VideoCapture(tmp_path)
        if cap.isOpened():
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                # Some formats don't report frame count — read sequentially
                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                skip = max(1, int(fps * 2))  # one frame every 2 seconds
                idx = 0
                while len(frames) < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if idx % skip == 0:
                        frames.append(frame)
                    idx += 1
            else:
                interval = max(1, total_frames // max_frames)
                for i in range(0, total_frames, interval):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frames.append(frame)
                    if len(frames) >= max_frames:
                        break
            cap.release()

        # Fallback 1: ffmpeg direct frame extraction (works with any format)
        if not frames and HAS_FFMPEG:
            frame_dir = tmp_path + "_frames"
            os.makedirs(frame_dir, exist_ok=True)
            try:
                # Extract evenly spaced frames directly as images
                subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_path,
                     "-vf", f"fps=1/2,scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
                     "-frames:v", str(max_frames),
                     "-q:v", "2",
                     os.path.join(frame_dir, "frame_%03d.jpg")],
                    capture_output=True, timeout=120,
                )
                frame_files = sorted(
                    f for f in os.listdir(frame_dir) if f.endswith(".jpg")
                )
                for fname in frame_files[:max_frames]:
                    img = cv2.imread(os.path.join(frame_dir, fname))
                    if img is not None:
                        frames.append(img)
            except Exception:
                pass
            finally:
                import shutil as _shutil
                _shutil.rmtree(frame_dir, ignore_errors=True)

        # Fallback 2: ffmpeg full conversion then cv2 read
        if not frames and HAS_FFMPEG:
            converted_path = tmp_path + "_converted.mp4"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_path, "-c:v", "libx264",
                     "-preset", "ultrafast", "-crf", "28",
                     "-vf", "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
                     converted_path],
                    capture_output=True, timeout=180,
                )
                if os.path.exists(converted_path):
                    cap = cv2.VideoCapture(converted_path)
                    if cap.isOpened():
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        interval = max(1, total_frames // max_frames)
                        for i in range(0, total_frames, interval):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                frames.append(frame)
                            if len(frames) >= max_frames:
                                break
                        cap.release()
            except Exception:
                pass
            finally:
                if os.path.exists(converted_path):
                    os.unlink(converted_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return frames


def _normalize_image(image_rgb: np.ndarray) -> np.ndarray:
    """Resize image to a workable dimension for face detection.
    Handles very large, very small, and oddly shaped images."""
    h, w = image_rgb.shape[:2]
    if h == 0 or w == 0:
        return image_rgb

    # If image is very large, downscale to MAX_DIMENSION
    if max(h, w) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        image_rgb = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # If image is very small, upscale so faces are at least detectable
    h, w = image_rgb.shape[:2]
    if max(h, w) < 200:
        scale = 400 / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        image_rgb = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return image_rgb


def _deduplicate_faces(face_results: list[dict]) -> list[dict]:
    """Remove duplicate face detections in the same image.
    If two bounding boxes detect the same person, keep the one with higher det_score."""
    if len(face_results) <= 1:
        return face_results

    engine = get_engine()
    unique = []
    used = set()

    for i, fr in enumerate(face_results):
        if i in used:
            continue
        unique.append(fr)
        for j in range(i + 1, len(face_results)):
            if j in used:
                continue
            sim = engine.cosine_similarity(fr["embedding"], face_results[j]["embedding"])
            if sim >= SAME_FACE_THRESHOLD:
                used.add(j)

    return unique


def _recognize_faces(
    image_data: bytes,
    known_embeddings: list[np.ndarray],
    known_names: list[str],
    known_photos: list[str],
    known_user_ids: list[int],
    known_branch_ids: list[int],
    visitor_embeddings: list[np.ndarray],
    visitor_ids: list[int],
    org_id: int,
):
    """Face recognition with bounding boxes using InsightFace (RetinaFace + ArcFace).
    Handles images of ANY format — cv2, PIL and ffmpeg fallbacks."""
    engine = get_engine()

    # Universal image decode: tries cv2 → PIL → ffmpeg
    bgr = _decode_any_image(image_data)
    if bgr is None:
        return b"", []

    image_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    image_rgb = _normalize_image(image_rgb)
    h, w = image_rgb.shape[:2]

    # Multi-pass detection with InsightFace
    face_results = engine.detect_and_encode_multi_pass(image_rgb)

    # Deduplicate: don't count the same face twice
    face_results = _deduplicate_faces(face_results)

    faces = []
    annotated = image_rgb.copy()
    seen_member_ids = set()
    seen_visitor_ids = set()

    for fr in face_results:
        x1, y1, x2, y2 = fr["bbox"]
        # Clamp to image bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        embedding = fr["embedding"]

        # Convert insightface bbox [x1,y1,x2,y2] to the app's [top,right,bottom,left] format
        top, right, bottom, left = y1, x2, y2, x1

        face_info = {
            "box": {"top": top, "right": right, "bottom": bottom, "left": left},
            "box_pct": {
                "top": round(top / h * 100, 2),
                "right": round(right / w * 100, 2),
                "bottom": round(bottom / h * 100, 2),
                "left": round(left / w * 100, 2),
            },
        }

        matched = False
        if known_embeddings:
            similarities = engine.cosine_distance_batch(known_embeddings, embedding)
            best_idx = int(np.argmax(similarities))
            best_sim = float(similarities[best_idx])

            if best_sim >= MEMBER_MATCH_THRESHOLD:
                uid = known_user_ids[best_idx] if known_user_ids else None
                if uid and uid in seen_member_ids:
                    continue
                if uid:
                    seen_member_ids.add(uid)

                face_info["type"] = "member"
                face_info["name"] = known_names[best_idx]
                face_info["confidence"] = round(best_sim, 2)
                face_info["photo"] = known_photos[best_idx] or ""
                face_info["user_id"] = uid
                face_info["branch_id"] = known_branch_ids[best_idx] if known_branch_ids else None
                face_info["_encoding"] = encode_embedding(embedding)  # store actual detected embedding
                matched = True
                cv2.rectangle(annotated, (left, top), (right, bottom), (37, 211, 102), 2)
                label = known_names[best_idx]
                (tw, th_t), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(annotated, (left, top - th_t - 10), (left + tw + 6, top), (37, 211, 102), -1)
                cv2.putText(annotated, label, (left + 3, top - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        if not matched:
            visitor_match_id = None
            if visitor_embeddings:
                v_sims = engine.cosine_distance_batch(visitor_embeddings, embedding)
                v_best = int(np.argmax(v_sims))
                if v_sims[v_best] >= VISITOR_MATCH_THRESHOLD:
                    visitor_match_id = visitor_ids[v_best]
                    if visitor_match_id in seen_visitor_ids:
                        continue
                    seen_visitor_ids.add(visitor_match_id)

            pad = 20
            crop_t, crop_b = max(0, top - pad), min(h, bottom + pad)
            crop_l, crop_r = max(0, left - pad), min(w, right + pad)
            face_crop = image_rgb[crop_t:crop_b, crop_l:crop_r]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"visitor_{org_id}_{ts}_{uuid.uuid4().hex[:6]}.jpg"
            cv2.imwrite(str(UNKNOWN_FACES_DIR / filename),
                        cv2.cvtColor(face_crop, cv2.COLOR_RGB2BGR))

            face_info["type"] = "visitor"
            face_info["name"] = "Unknown"
            face_info["face_crop"] = f"/static/unknown_faces/{filename}"
            face_info["_encoding"] = encode_embedding(embedding)
            face_info["visitor_match_id"] = visitor_match_id

            cv2.rectangle(annotated, (left, top), (right, bottom), (255, 159, 10), 2)
            (tw, th_t), _ = cv2.getTextSize("NEW?", cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (left, top - th_t - 10), (left + tw + 6, top), (255, 159, 10), -1)
            cv2.putText(annotated, "NEW?", (left + 3, top - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        faces.append(face_info)

    annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
    _, buf = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes(), faces


def _load_known_embeddings(users):
    """Load known member embeddings from DB, filtering by embedding version.

    Returns members with ArcFace embeddings for matching, and a list of
    members who still have old dlib embeddings (need re-registration).
    """
    known_embeddings = []
    known_names = []
    known_photos = []
    known_user_ids = []
    known_branch_ids = []
    needs_reregister = []

    for u in users:
        emb, version = decode_embedding(u.face_embedding)
        if emb is None:
            needs_reregister.append(u.name)
            continue
        if version == "arcface":
            known_embeddings.append(emb)
            known_names.append(u.name)
            known_photos.append(u.profile_photo)
            known_user_ids.append(u.id)
            known_branch_ids.append(getattr(u, 'branch_id', None))
        else:
            # Old dlib embedding — can't compare with ArcFace
            needs_reregister.append(u.name)

    return known_embeddings, known_names, known_photos, known_user_ids, known_branch_ids, needs_reregister


def _load_visitor_embeddings(visitors):
    """Load visitor embeddings, only ArcFace versions."""
    visitor_embeddings = []
    visitor_ids = []
    for v in visitors:
        if v.face_embedding:
            emb, version = decode_embedding(v.face_embedding)
            if emb is not None and version == "arcface":
                visitor_embeddings.append(emb)
                visitor_ids.append(v.id)
    return visitor_embeddings, visitor_ids


@router.post("/recognize")
async def recognize_face(
    file: UploadFile = File(...),
    meeting_id: Optional[int] = Form(None),
    branch_id: Optional[int] = Form(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Recognize faces, draw bounding boxes, capture unknown visitors."""
    try:
        return await _recognize_face_inner(file, meeting_id, branch_id, admin, db)
    except Exception as exc:
        logger.error("recognize error: %s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": f"Recognition failed: {exc}"})


async def _recognize_face_inner(file, meeting_id, branch_id, admin, db):
    image_data = await file.read()

    effective_branch_id = branch_id
    if admin.role != "owner" and admin.branch_id:
        if branch_id and branch_id != admin.branch_id:
            raise HTTPException(status_code=403, detail="You can only access your assigned branch")
        effective_branch_id = admin.branch_id

    # Resolve meeting if provided
    meeting = None
    meeting_name = None
    late_after_minutes = None
    if meeting_id:
        meeting = db.query(Meeting).filter(
            Meeting.id == meeting_id, Meeting.org_id == admin.org_id
        ).first()
        if meeting:
            if admin.role != "owner" and admin.branch_id and meeting.branch_id != admin.branch_id:
                raise HTTPException(status_code=403, detail="Meeting is outside your assigned branch")
            meeting_name = meeting.name
            late_after_minutes = getattr(meeting, 'late_after_minutes', None)

    # Get members from the organization
    user_query = db.query(User).filter(User.org_id == admin.org_id)
    if effective_branch_id:
        user_query = user_query.filter(
            or_(User.branch_id == effective_branch_id, User.is_global == True, User.branch_id == None)
        )
    users = user_query.all()

    known_embeddings, known_names, known_photos, known_user_ids, known_branch_ids, needs_reregister = \
        _load_known_embeddings(users)

    visitors_query = db.query(Visitor).filter(Visitor.org_id == admin.org_id)
    if effective_branch_id:
        visitors_query = visitors_query.filter(Visitor.branch_id == effective_branch_id)
    visitors = visitors_query.all()
    visitor_embeddings, visitor_ids = _load_visitor_embeddings(visitors)

    annotated_jpg, faces = await asyncio.to_thread(
        _recognize_faces, image_data,
        known_embeddings, known_names, known_photos, known_user_ids, known_branch_ids,
        visitor_embeddings, visitor_ids, admin.org_id,
    )

    recognized_members = []
    member_photo_map = {}
    member_user_ids = {}
    member_branch_ids = {}
    new_visitors = []
    already_marked_visitors = []

    for face in faces:
        if face["type"] == "member":
            if face["name"] not in recognized_members:
                recognized_members.append(face["name"])
                member_photo_map[face["name"]] = face.get("photo", "")
                member_user_ids[face["name"]] = face.get("user_id")
                member_branch_ids[face["name"]] = face.get("branch_id")
        elif face["type"] == "visitor":
            raw_enc = face.pop("_encoding", None)
            vmid = face.get("visitor_match_id")

            def _visitor_already_marked(vid):
                now = datetime.utcnow()
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                vq = db.query(Attendance).filter(
                    Attendance.org_id == admin.org_id,
                    Attendance.visitor_id == vid,
                    Attendance.time >= today_start,
                )
                if meeting_id:
                    vq = vq.filter(Attendance.meeting_id == meeting_id)
                return vq.first() is not None

            if vmid:
                v = db.query(Visitor).filter(Visitor.id == vmid, Visitor.org_id == admin.org_id).first()
                if v:
                    v.visit_count += 1
                    v.last_seen = datetime.utcnow()
                    if effective_branch_id and not v.branch_id:
                        v.branch_id = effective_branch_id
                    new_visitors.append({
                        "id": v.id, "face_photo": v.face_photo,
                        "label": v.label, "visit_count": v.visit_count,
                        "is_returning": True,
                    })
                    if _visitor_already_marked(v.id):
                        already_marked_visitors.append({
                            "id": v.id,
                            "label": v.label or f"Visitor #{v.id}",
                        })
                    else:
                        db.add(Attendance(
                            org_id=admin.org_id,
                            name=v.label or f"Visitor #{v.id}",
                            time=datetime.utcnow(),
                            member_type="visitor",
                            visitor_id=v.id,
                            profile_photo=v.face_photo,
                            branch_id=effective_branch_id,
                            meeting_id=meeting_id if meeting else None,
                            meeting_name=meeting_name,
                        ))
            else:
                v = Visitor(
                    org_id=admin.org_id,
                    face_photo=face["face_crop"],
                    face_embedding=raw_enc,
                    branch_id=effective_branch_id,
                )
                db.add(v)
                db.flush()
                new_visitors.append({
                    "id": v.id, "face_photo": face["face_crop"],
                    "label": None, "visit_count": 1,
                    "is_returning": False,
                })
                db.add(Attendance(
                    org_id=admin.org_id,
                    name=f"Visitor #{v.id}",
                    time=datetime.utcnow(),
                    member_type="visitor",
                    visitor_id=v.id,
                    profile_photo=face["face_crop"],
                    branch_id=effective_branch_id,
                    meeting_id=meeting_id if meeting else None,
                    meeting_name=meeting_name,
                ))

    # Mark attendance for members not already marked today (per meeting)
    already_marked_today = []
    newly_marked = []
    if recognized_members:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for n in recognized_members:
            dup_q = (
                db.query(Attendance)
                .filter(
                    Attendance.org_id == admin.org_id,
                    Attendance.name == n,
                    Attendance.time >= today_start,
                )
            )
            if meeting_id:
                dup_q = dup_q.filter(Attendance.meeting_id == meeting_id)
            existing = dup_q.first()

            if existing:
                already_marked_today.append(n)
            else:
                is_late = False
                late_minutes = 0
                if meeting and late_after_minutes:
                    pass  # Lateness logic can be enhanced based on meeting schedule

                user_id = member_user_ids.get(n)
                member_branch_id = member_branch_ids.get(n)
                marked_at_branch_id = effective_branch_id
                is_cross_branch = member_branch_id and effective_branch_id and member_branch_id != effective_branch_id

                db.add(Attendance(
                    org_id=admin.org_id,
                    name=n,
                    time=now,
                    profile_photo=member_photo_map.get(n, ""),
                    member_type="member",
                    meeting_id=meeting_id if meeting else None,
                    meeting_name=meeting_name,
                    user_id=user_id,
                    branch_id=member_branch_id or effective_branch_id,
                    marked_at_branch_id=marked_at_branch_id,
                    is_late=is_late,
                    late_minutes=late_minutes,
                ))
                newly_marked.append(n)

    db.commit()

    # Send SMS notifications for newly marked members (non-blocking)
    if newly_marked and is_sms_configured():
        org = db.query(Organization).filter(Organization.id == admin.org_id).first()
        org_name = org.name if org else None
        for name in newly_marked:
            user = db.query(User).filter(User.name == name, User.org_id == admin.org_id).first()
            if user and user.phone:
                try:
                    send_attendance_sms(user.phone, name, meeting_name, org_name)
                except Exception:
                    pass  # Don't fail attendance over SMS errors

    clean_faces = []
    for f in faces:
        c = {"box": f["box"], "box_pct": f["box_pct"], "type": f["type"], "name": f.get("name", "Unknown")}
        if f["type"] == "member":
            c["confidence"] = f.get("confidence", 0)
            c["photo"] = f.get("photo", "")
        else:
            c["face_crop"] = f.get("face_crop", "")
            c["visitor_match_id"] = f.get("visitor_match_id")
        clean_faces.append(c)

    result = {
        "total_faces": len(faces),
        "recognized": [f["name"] for f in faces],
        "attendance_marked": newly_marked,
        "already_marked_today": already_marked_today,
        "already_marked_visitors": already_marked_visitors,
        "annotated_image": base64.b64encode(annotated_jpg).decode("ascii") if annotated_jpg else "",
        "faces": clean_faces,
        "new_visitors": new_visitors,
    }

    # Warn frontend if some members need re-registration with new model
    if needs_reregister:
        result["needs_reregister"] = needs_reregister

    return result


@router.post("/recognize-video")
async def recognize_video(
    file: UploadFile = File(...),
    meeting_id: Optional[int] = Form(None),
    branch_id: Optional[int] = Form(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Process a video of ANY format — extract frames, recognize faces in each,
    and mark attendance for everyone found.
    """
    try:
        return await _recognize_video_inner(file, meeting_id, branch_id, admin, db)
    except Exception as exc:
        logger.error("recognize-video error: %s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": f"Video recognition failed: {exc}"})


async def _recognize_video_inner(file, meeting_id, branch_id, admin, db):
    video_data = await file.read()

    effective_branch_id = branch_id
    if admin.role != "owner" and admin.branch_id:
        if branch_id and branch_id != admin.branch_id:
            raise HTTPException(status_code=403, detail="You can only access your assigned branch")
        effective_branch_id = admin.branch_id

    # Resolve meeting
    meeting = None
    meeting_name = None
    if meeting_id:
        meeting = db.query(Meeting).filter(
            Meeting.id == meeting_id, Meeting.org_id == admin.org_id
        ).first()
        if meeting:
            if admin.role != "owner" and admin.branch_id and meeting.branch_id != admin.branch_id:
                raise HTTPException(status_code=403, detail="Meeting is outside your assigned branch")
            meeting_name = meeting.name

    # Load known members & visitors
    user_query = db.query(User).filter(User.org_id == admin.org_id)
    if effective_branch_id:
        user_query = user_query.filter(
            or_(User.branch_id == effective_branch_id, User.is_global == True, User.branch_id == None)
        )
    users = user_query.all()

    known_embeddings, known_names, known_photos, known_user_ids, known_branch_ids, needs_reregister = \
        _load_known_embeddings(users)

    visitors_query = db.query(Visitor).filter(Visitor.org_id == admin.org_id)
    if effective_branch_id:
        visitors_query = visitors_query.filter(Visitor.branch_id == effective_branch_id)
    visitors = visitors_query.all()
    visitor_embeddings, visitor_ids = _load_visitor_embeddings(visitors)

    # Extract frames from the video (any format, any size)
    frames_bgr = await asyncio.to_thread(_extract_video_frames, video_data, 10)
    if not frames_bgr:
        return {"error": "Could not read video. Supported formats: MP4, MOV, AVI, MKV, WebM, FLV, and more.", "total_faces": 0}

    engine = get_engine()

    # ── Collect all face embeddings from all frames ──
    all_frame_faces = []  # list of (frame_index, face_info_with_embedding)
    annotated_images = []
    all_raw_embeddings = []  # parallel list of np.ndarray embeddings for every face

    for fi, frame_bgr in enumerate(frames_bgr):
        _, jpeg_buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        frame_bytes = jpeg_buf.tobytes()

        annotated_jpg, faces = await asyncio.to_thread(
            _recognize_faces, frame_bytes,
            known_embeddings, known_names, known_photos, known_user_ids, known_branch_ids,
            visitor_embeddings, visitor_ids, admin.org_id,
        )
        for f in faces:
            # Extract the actual detected embedding for cross-frame comparison
            raw_enc = f.get("_encoding")
            emb = None
            if raw_enc:
                emb, _ = decode_embedding(raw_enc)
            all_frame_faces.append((fi, f))
            all_raw_embeddings.append(emb)
        if annotated_jpg:
            annotated_images.append(base64.b64encode(annotated_jpg).decode("ascii"))

    # ── Global cross-frame dedup: group ALL faces (members + visitors) by embedding ──
    # Uses centroid-based grouping: compare each face against the AVERAGE embedding
    # of existing groups for more robust matching across pose/angle changes.
    num_faces = len(all_frame_faces)
    face_group = [-1] * num_faces
    group_centroids = []  # list of (sum_embedding, count) per group
    group_counter = 0

    for i in range(num_faces):
        if face_group[i] >= 0:
            continue
        emb_i = all_raw_embeddings[i]
        if emb_i is None:
            face_group[i] = group_counter
            group_centroids.append(None)
            group_counter += 1
            continue

        # Try to merge into an existing group by comparing to centroids
        best_group = -1
        best_sim = -1
        for g_idx in range(group_counter):
            if group_centroids[g_idx] is None:
                continue
            centroid_sum, cnt = group_centroids[g_idx]
            centroid = centroid_sum / cnt
            sim = float(engine.cosine_similarity(emb_i, centroid))
            if sim >= VIDEO_SAME_FACE_THRESHOLD and sim > best_sim:
                best_sim = sim
                best_group = g_idx

        if best_group >= 0:
            face_group[i] = best_group
            c_sum, cnt = group_centroids[best_group]
            group_centroids[best_group] = (c_sum + emb_i, cnt + 1)
        else:
            face_group[i] = group_counter
            group_centroids.append((emb_i.copy(), 1))
            group_counter += 1

    # ── For each group, decide: member (if ANY frame matched a member) or visitor ──
    recognized_members = []
    member_photo_map = {}
    member_user_ids_map = {}
    member_branch_ids_map = {}
    unique_visitor_groups = []

    for g in range(group_counter):
        group_indices = [i for i in range(num_faces) if face_group[i] == g]
        group_faces = [all_frame_faces[i][1] for i in group_indices]

        # Check if any face in this group was recognized as a member
        member_face = None
        for f in group_faces:
            if f["type"] == "member":
                member_face = f
                break

        if member_face:
            name = member_face["name"]
            if name not in recognized_members:
                recognized_members.append(name)
                member_photo_map[name] = member_face.get("photo", "")
                member_user_ids_map[name] = member_face.get("user_id")
                member_branch_ids_map[name] = member_face.get("branch_id")
        else:
            # All faces in this group are visitors — pick best embedding
            best_enc = None
            best_vmid = None
            best_crop = ""
            for idx in group_indices:
                f = all_frame_faces[idx][1]
                if f.get("_encoding") and not best_enc:
                    best_enc = f["_encoding"]
                if f.get("visitor_match_id") and not best_vmid:
                    best_vmid = f["visitor_match_id"]
                if f.get("face_crop") and not best_crop:
                    best_crop = f["face_crop"]
            if best_enc:
                emb, _ = decode_embedding(best_enc)
                if emb is not None:
                    unique_visitor_groups.append({
                        "embedding": emb,
                        "raw_enc": best_enc,
                        "visitor_match_id": best_vmid,
                        "face_crop": best_crop,
                    })

    # ── Now process each unique visitor group ──
    new_visitors_list = []
    already_marked_visitors = []
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for group in unique_visitor_groups:
        vmid = group["visitor_match_id"]

        # Check DB for already-marked attendance
        def _visitor_already_marked(vid):
            vq = db.query(Attendance).filter(
                Attendance.org_id == admin.org_id,
                Attendance.visitor_id == vid,
                Attendance.time >= today_start,
            )
            if meeting_id:
                vq = vq.filter(Attendance.meeting_id == meeting_id)
            return vq.first() is not None

        if vmid:
            # Known returning visitor
            v = db.query(Visitor).filter(Visitor.id == vmid, Visitor.org_id == admin.org_id).first()
            if v:
                if _visitor_already_marked(v.id):
                    already_marked_visitors.append({"id": v.id, "label": v.label or f"Visitor #{v.id}"})
                else:
                    v.visit_count += 1
                    v.last_seen = datetime.utcnow()
                    if effective_branch_id and not v.branch_id:
                        v.branch_id = effective_branch_id
                    new_visitors_list.append({"id": v.id, "label": v.label, "is_returning": True})
                    db.add(Attendance(
                        org_id=admin.org_id,
                        name=v.label or f"Visitor #{v.id}",
                        time=datetime.utcnow(),
                        member_type="visitor",
                        visitor_id=v.id,
                        branch_id=effective_branch_id,
                        meeting_id=meeting_id if meeting else None,
                        meeting_name=meeting_name,
                    ))
        else:
            # Brand new visitor — create exactly ONE record
            v = Visitor(
                org_id=admin.org_id,
                face_photo=group["face_crop"],
                face_embedding=group["raw_enc"],
                branch_id=effective_branch_id,
            )
            db.add(v)
            db.flush()
            new_visitors_list.append({"id": v.id, "label": None, "is_returning": False})
            db.add(Attendance(
                org_id=admin.org_id,
                name=f"Visitor #{v.id}",
                time=datetime.utcnow(),
                member_type="visitor",
                visitor_id=v.id,
                branch_id=effective_branch_id,
                meeting_id=meeting_id if meeting else None,
                meeting_name=meeting_name,
            ))

    # ── Mark member attendance (once per member per meeting) ──
    already_marked = []
    newly_marked = []
    now = datetime.utcnow()
    for n in recognized_members:
        dup_q = db.query(Attendance).filter(
            Attendance.org_id == admin.org_id,
            Attendance.name == n,
            Attendance.time >= today_start,
        )
        if meeting_id:
            dup_q = dup_q.filter(Attendance.meeting_id == meeting_id)
        if dup_q.first():
            already_marked.append(n)
        else:
            user_id = member_user_ids_map.get(n)
            member_branch_id = member_branch_ids_map.get(n)
            db.add(Attendance(
                org_id=admin.org_id,
                name=n,
                time=now,
                profile_photo=member_photo_map.get(n, ""),
                member_type="member",
                meeting_id=meeting_id if meeting else None,
                meeting_name=meeting_name,
                user_id=user_id,
                branch_id=member_branch_id or effective_branch_id,
                marked_at_branch_id=effective_branch_id,
            ))
            newly_marked.append(n)

    db.commit()

    # Send SMS notifications for newly marked members (non-blocking)
    if newly_marked and is_sms_configured():
        org = db.query(Organization).filter(Organization.id == admin.org_id).first()
        org_name = org.name if org else None
        for name in newly_marked:
            user = db.query(User).filter(User.name == name, User.org_id == admin.org_id).first()
            if user and user.phone:
                try:
                    send_attendance_sms(user.phone, name, meeting_name, org_name)
                except Exception:
                    pass

    return {
        "total_faces": len(all_frame_faces),
        "frames_processed": len(frames_bgr),
        "recognized": recognized_members,
        "attendance_marked": newly_marked,
        "already_marked_today": already_marked,
        "already_marked_visitors": already_marked_visitors,
        "annotated_frames": annotated_images,
        "new_visitors": new_visitors_list,
    }
