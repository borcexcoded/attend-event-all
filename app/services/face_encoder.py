from app.face_engine import get_engine


def encode_face(image, face_locations=None):
    """Encode faces found in image using InsightFace ArcFace."""
    engine = get_engine()
    results = engine.detect_and_encode(image)
    return [r["embedding"] for r in results]
