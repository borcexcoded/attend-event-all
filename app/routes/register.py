"""
Member Registration Route — powered by InsightFace (RetinaFace + ArcFace)
=========================================================================
Registers new members with their face photo. Uses SOTA face detection and
512-d ArcFace embeddings for reliable identification across all skin tones.
"""

import asyncio
import io
import json
import os
import uuid
import subprocess
import tempfile
import shutil

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import numpy as np
import cv2
from PIL import Image

from app.database import get_db
from app.models.user import User
from app.models.organization import Admin
from app.models.branch import Branch
from app.models.registration_field import RegistrationField, MemberCustomData
from app.auth import get_current_admin
from app.face_engine import (
    get_engine,
    decode_embedding,
    encode_embedding,
    DUPLICATE_REGISTER_THRESHOLD,
    _enhance_for_detection,
)

router = APIRouter(tags=["Members"])

MAX_DIMENSION = 1600
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _normalize_image_bytes(image_data: bytes) -> np.ndarray | None:
    """Decode and normalize image of ANY format for reliable face detection.
    Tries cv2 → PIL → ffmpeg fallback."""
    # 1. Try cv2
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 2. Try PIL (handles HEIC, AVIF, WebP, etc.)
    if img is None:
        try:
            pil_img = Image.open(io.BytesIO(image_data))
            pil_img = pil_img.convert("RGB")
            rgb = np.array(pil_img)
            img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            pass

    # 3. Last resort — ffmpeg
    if img is None and HAS_FFMPEG:
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
                img = cv2.imread(tmp_out_path)
                os.unlink(tmp_out_path)
            os.unlink(tmp_in_path)
        except Exception:
            pass

    if img is None:
        return None

    h, w = img.shape[:2]
    # Downscale very large images
    if max(h, w) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    # Upscale very small images
    h, w = img.shape[:2]
    if max(h, w) < 200:
        scale = 400 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Convert BGR -> RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return rgb


def _get_face_embeddings(image_data: bytes) -> list[np.ndarray]:
    """Blocking function to detect faces and compute 512-d ArcFace embeddings.
    Uses multi-pass detection for maximum recall."""
    rgb = _normalize_image_bytes(image_data)
    if rgb is None:
        return []

    engine = get_engine()
    # Multi-pass detection catches hard cases (dark skin, low light, small faces)
    face_results = engine.detect_and_encode_multi_pass(rgb)
    return [fr["embedding"] for fr in face_results]


def _check_duplicate_face(
    embedding: np.ndarray,
    existing_embeddings: list[np.ndarray],
    existing_names: list[str],
) -> str | None:
    """Check if the embedding matches any existing member. Returns name if duplicate."""
    if not existing_embeddings:
        return None
    engine = get_engine()
    similarities = engine.cosine_distance_batch(existing_embeddings, embedding)
    best_idx = int(np.argmax(similarities))
    if similarities[best_idx] >= DUPLICATE_REGISTER_THRESHOLD:
        return existing_names[best_idx]
    return None


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    name: str = Form(...),
    file: UploadFile = File(...),
    email: str = Form(None),
    phone: str = Form(None),
    branch_id: int = Form(None),
    custom_fields: str = Form(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Register a new member with their face photo. Checks for duplicate faces."""
    effective_branch_id = branch_id
    if admin.role != "owner" and admin.branch_id:
        if branch_id and branch_id != admin.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only register members in your assigned branch.",
            )
        effective_branch_id = admin.branch_id
    elif branch_id:
        branch = db.query(Branch).filter(
            Branch.id == branch_id,
            Branch.org_id == admin.org_id,
            Branch.is_active == True,
        ).first()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Branch not found in your organization.",
            )

    if db.query(User).filter(User.name == name, User.org_id == admin.org_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Member '{name}' already exists.",
        )

    image_data = await file.read()
    face_embeddings = await asyncio.to_thread(_get_face_embeddings, image_data)

    if len(face_embeddings) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected in the uploaded image. Please upload a clear photo.",
        )

    if len(face_embeddings) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple faces detected. Please upload a photo with only one face.",
        )

    new_embedding = face_embeddings[0]

    # Check for duplicate face across all members in this org
    all_users = db.query(User).filter(User.org_id == admin.org_id).all()
    existing_embeddings = []
    existing_names = []
    for u in all_users:
        emb, version = decode_embedding(u.face_embedding)
        if emb is not None and version == "arcface":
            existing_embeddings.append(emb)
            existing_names.append(u.name)

    dup_name = await asyncio.to_thread(
        _check_duplicate_face, new_embedding, existing_embeddings, existing_names
    )
    if dup_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This face closely matches existing member '{dup_name}'. "
                   f"The same face cannot be registered twice with a different name. "
                   f"If this is a twin or different person, please contact an admin to override.",
        )

    photo_dir = f"app/static/photos/{admin.org_id}"
    os.makedirs(photo_dir, exist_ok=True)
    photo_filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = f"{photo_dir}/{photo_filename}"
    with open(photo_path, "wb") as f:
        f.write(image_data)

    face_embedding_bytes = encode_embedding(new_embedding)
    new_user = User(
        org_id=admin.org_id,
        name=name,
        face_embedding=face_embedding_bytes,
        profile_photo=f"/static/photos/{admin.org_id}/{photo_filename}",
        email=email,
        phone=phone,
        branch_id=effective_branch_id,
        is_global=effective_branch_id is None,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Save custom field values
    if custom_fields:
        try:
            cf_data = json.loads(custom_fields)  # expects {"field_id": "value", ...}
            for field_id_str, value in cf_data.items():
                field_id = int(field_id_str)
                # Verify field belongs to this org
                field = db.query(RegistrationField).filter(
                    RegistrationField.id == field_id,
                    RegistrationField.org_id == admin.org_id,
                    RegistrationField.is_active == True,
                ).first()
                if field and value:
                    db.add(MemberCustomData(
                        org_id=admin.org_id,
                        user_id=new_user.id,
                        field_id=field_id,
                        value=str(value),
                    ))
            db.commit()
        except (json.JSONDecodeError, ValueError):
            pass  # ignore malformed custom_fields

    return {"message": f"Member '{name}' registered successfully.", "id": new_user.id}


@router.post("/re-register/{user_id}", status_code=status.HTTP_200_OK)
async def re_register_face(
    user_id: int,
    file: UploadFile = File(...),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Re-register a member's face with the new SOTA model.
    Use this to upgrade members from the old dlib embeddings to ArcFace."""
    user = db.query(User).filter(
        User.id == user_id, User.org_id == admin.org_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found.")
    if admin.role != "owner" and admin.branch_id and user.branch_id != admin.branch_id:
        raise HTTPException(status_code=403, detail="You can only update members in your assigned branch.")

    image_data = await file.read()
    face_embeddings = await asyncio.to_thread(_get_face_embeddings, image_data)

    if len(face_embeddings) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected. Please upload a clear photo.",
        )
    if len(face_embeddings) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple faces detected. Please upload a photo with only one face.",
        )

    new_embedding = face_embeddings[0]

    # Update profile photo
    photo_dir = f"app/static/photos/{admin.org_id}"
    os.makedirs(photo_dir, exist_ok=True)
    photo_filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = f"{photo_dir}/{photo_filename}"
    with open(photo_path, "wb") as f:
        f.write(image_data)

    user.face_embedding = encode_embedding(new_embedding)
    user.profile_photo = f"/static/photos/{admin.org_id}/{photo_filename}"
    db.commit()

    return {
        "message": f"Member '{user.name}' face re-registered with SOTA model.",
        "id": user.id,
    }
