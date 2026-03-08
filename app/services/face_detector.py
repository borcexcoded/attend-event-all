from app.face_engine import get_engine


def detect_faces(image):
    """Detect face locations in an image using InsightFace RetinaFace."""
    engine = get_engine()
    results = engine.detect_and_encode(image)
    # Return in (top, right, bottom, left) format for compatibility
    return [(r["bbox"][1], r["bbox"][2], r["bbox"][3], r["bbox"][0]) for r in results]
