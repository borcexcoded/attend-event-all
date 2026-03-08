"""
SOTA Face Detection & Recognition Engine
=========================================
Uses insightface (RetinaFace detector + ArcFace recognizer) for state-of-the-art
face analysis that works reliably across all skin tones, lighting conditions,
and face angles.

- RetinaFace: SOTA face detector, trained on WIDER FACE dataset
- ArcFace: SOTA face recognizer, 99.83% on LFW, 512-d embeddings
- Both models are trained on racially diverse datasets (MS1MV2, Glint360K)

Embedding format: 512-d float32 (2048 bytes when stored as raw bytes)
Similarity metric: cosine similarity (higher = more similar, range -1 to 1)
"""

import logging
import os
import threading
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Lazy singleton — model loads on first use
_engine_instance = None
_engine_lock = threading.Lock()

# Thresholds tuned for ArcFace cosine similarity
# Higher = stricter matching.  ArcFace typical ranges:
#   same person: 0.3 – 0.8+
#   different person: < 0.2
MEMBER_MATCH_THRESHOLD = 0.35       # Relaxed for better recall across angles/lighting
VISITOR_MATCH_THRESHOLD = 0.40      # Visitors need a bit stricter to avoid false re-matches
SAME_FACE_THRESHOLD = 0.48          # Duplicate face in same frame (high similarity expected)
VIDEO_SAME_FACE_THRESHOLD = 0.32   # Cross-frame dedup in video (lower to handle pose/angle changes)
DUPLICATE_REGISTER_THRESHOLD = 0.48 # Duplicate face at registration time

# Detection parameters
DET_THRESH = 0.5   # Face detection confidence threshold
DET_SIZE = (640, 640)  # Detection input size


def _patch_albumentations():
    """Bypass the slow albumentations import that insightface pulls in.
    albumentations triggers pydantic plugin scanning across all conda packages,
    which can hang for minutes. We only need FaceAnalysis (RetinaFace + ArcFace),
    not the mask_renderer that requires albumentations."""
    import sys
    import types
    if 'albumentations' in sys.modules:
        return  # Already imported properly
    alb = types.ModuleType('albumentations')
    alb.core = types.ModuleType('albumentations.core')
    alb.core.transforms_interface = types.ModuleType(
        'albumentations.core.transforms_interface'
    )
    # Provide the class that mask_renderer expects
    alb.core.transforms_interface.ImageOnlyTransform = type(
        'ImageOnlyTransform', (), {}
    )
    sys.modules['albumentations'] = alb
    sys.modules['albumentations.core'] = alb.core
    sys.modules['albumentations.core.transforms_interface'] = (
        alb.core.transforms_interface
    )


def _enhance_for_detection(image_rgb: np.ndarray) -> np.ndarray:
    """Apply CLAHE and adaptive gamma correction to improve face detection
    across all skin tones. Operates in LAB colour space so only lightness
    is modified — skin colour information is preserved."""
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)

    # Adaptive gamma: brighten dark images
    mean_l = float(l_enhanced.mean())
    if mean_l < 110:
        gamma = max(0.5, mean_l / 140.0)
        inv_gamma = 1.0 / gamma
        table = np.array(
            [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
            dtype=np.uint8,
        )
        l_enhanced = cv2.LUT(l_enhanced, table)

    lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)


class FaceEngine:
    """Singleton wrapper around insightface FaceAnalysis.
    
    Thread-safe for read-only inference (the ONNX session handles concurrent reads).
    Model files are downloaded automatically on first run (~300 MB buffalo_l pack).
    """

    def __init__(self):
        _patch_albumentations()  # Fast-path: bypass slow albumentations import
        from insightface.app.face_analysis import FaceAnalysis

        # Use buffalo_l (large) model pack — best accuracy
        # Downloads to ~/.insightface/models/buffalo_l on first run
        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=_get_providers(),
        )
        self.app.prepare(ctx_id=0, det_thresh=DET_THRESH, det_size=DET_SIZE)
        logger.info("InsightFace engine loaded (buffalo_l, providers=%s)", _get_providers())

    def detect_and_encode(self, image_rgb: np.ndarray) -> list[dict]:
        """Detect all faces and compute 512-d ArcFace embeddings.
        
        Args:
            image_rgb: RGB numpy array (H, W, 3)
        
        Returns:
            List of dicts with keys:
                - bbox: [x1, y1, x2, y2] (pixel coords)
                - embedding: np.ndarray shape (512,) dtype float32
                - det_score: float detection confidence
                - kps: 5-point facial landmarks (optional)
        """
        # insightface expects BGR input
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        faces = self.app.get(image_bgr)

        results = []
        for face in faces:
            results.append({
                "bbox": face.bbox.astype(int).tolist(),  # [x1, y1, x2, y2]
                "embedding": face.normed_embedding,       # 512-d, L2-normalised
                "det_score": float(face.det_score),
                "kps": face.kps.tolist() if face.kps is not None else None,
            })
        return results

    def detect_and_encode_multi_pass(self, image_rgb: np.ndarray) -> list[dict]:
        """Multi-pass detection for hard cases: tries with original image,
        then with enhanced contrast, then at higher resolution.
        
        This catches faces that a single pass might miss (dark skin in
        low light, small faces, profile angles).
        """
        # Pass 1: original image
        results = self.detect_and_encode(image_rgb)
        if results:
            return results

        # Pass 2: CLAHE-enhanced image
        enhanced = _enhance_for_detection(image_rgb)
        results = self.detect_and_encode(enhanced)
        if results:
            return results

        # Pass 3: upscale small images and try again
        h, w = image_rgb.shape[:2]
        if max(h, w) < 640:
            scale = 640 / max(h, w)
            bigger = cv2.resize(
                image_rgb,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_CUBIC,
            )
            results_big = self.detect_and_encode(bigger)
            if results_big:
                # Scale bounding boxes back to original dimensions
                for r in results_big:
                    r["bbox"] = [
                        int(r["bbox"][0] / scale),
                        int(r["bbox"][1] / scale),
                        int(r["bbox"][2] / scale),
                        int(r["bbox"][3] / scale),
                    ]
                return results_big

        # Pass 4: enhance + upscale combined
        enhanced = _enhance_for_detection(image_rgb)
        if max(h, w) < 640:
            scale = 640 / max(h, w)
            enhanced = cv2.resize(
                enhanced,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_CUBIC,
            )
        else:
            scale = 1.0

        results_final = self.detect_and_encode(enhanced)
        if results_final and scale != 1.0:
            for r in results_final:
                r["bbox"] = [
                    int(r["bbox"][0] / scale),
                    int(r["bbox"][1] / scale),
                    int(r["bbox"][2] / scale),
                    int(r["bbox"][3] / scale),
                ]
        return results_final

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings.
        Both ArcFace embeddings are already L2-normalised, so this is just a dot product."""
        return float(np.dot(emb1, emb2))

    @staticmethod
    def cosine_distance_batch(known_embeddings: list[np.ndarray], query: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between a query embedding and a list of known embeddings.
        Returns array of similarities (higher = more similar)."""
        if not known_embeddings:
            return np.array([])
        known = np.array(known_embeddings)  # (N, 512)
        # Dot product (embeddings are already L2-normalised)
        sims = known @ query  # (N,)
        return sims


def _get_providers() -> list[str]:
    """Select ONNX runtime execution providers based on platform."""
    providers = []
    try:
        import onnxruntime
        available = onnxruntime.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        # Skip CoreMLExecutionProvider — it crashes on macOS when saving
        # temporary .mlmodel files to /var/folders (permission / sandbox issue).
    except ImportError:
        pass
    providers.append("CPUExecutionProvider")
    return providers


def get_engine() -> FaceEngine:
    """Get the singleton FaceEngine instance (lazy-loaded on first call).
    Thread-safe: uses a lock to prevent double initialization."""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                logger.info("Initialising InsightFace engine (first call, downloading models if needed)...")
                _engine_instance = FaceEngine()
    return _engine_instance


# ---------------------------------------------------------------------------
# Embedding compatibility helpers
# ---------------------------------------------------------------------------
# Old dlib embeddings: 128 × float64 = 1024 bytes
# New ArcFace embeddings: 512 × float32 = 2048 bytes

DLIB_EMBEDDING_BYTES = 128 * 8   # 1024
ARCFACE_EMBEDDING_BYTES = 512 * 4  # 2048


def decode_embedding(raw: bytes) -> tuple[np.ndarray | None, str]:
    """Decode a raw embedding from the database.
    
    Returns:
        (embedding_array, version_string)
        version_string is either 'arcface' or 'dlib'
        Returns (None, 'unknown') if the format is unrecognised.
    """
    if raw is None:
        return None, "unknown"
    nbytes = len(raw)
    if nbytes == ARCFACE_EMBEDDING_BYTES:
        return np.frombuffer(raw, dtype=np.float32).copy(), "arcface"
    elif nbytes == DLIB_EMBEDDING_BYTES:
        return np.frombuffer(raw, dtype=np.float64).copy(), "dlib"
    else:
        # Try float32 first for any other size
        try:
            arr = np.frombuffer(raw, dtype=np.float32).copy()
            if arr.shape[0] == 512:
                return arr, "arcface"
        except Exception:
            pass
        try:
            arr = np.frombuffer(raw, dtype=np.float64).copy()
            if arr.shape[0] == 128:
                return arr, "dlib"
        except Exception:
            pass
        return None, "unknown"


def encode_embedding(embedding: np.ndarray) -> bytes:
    """Encode a 512-d ArcFace embedding to raw bytes for DB storage."""
    return embedding.astype(np.float32).tobytes()
