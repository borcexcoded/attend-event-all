import numpy as np
from app.face_engine import get_engine


def match_face(known_encodings, known_names, unknown_encoding, threshold=0.38):
    """Match an unknown face encoding against known encodings using cosine similarity."""
    if not known_encodings:
        return "UNKNOWN"
    engine = get_engine()
    sims = engine.cosine_distance_batch(known_encodings, unknown_encoding)
    best_idx = int(np.argmax(sims))
    if sims[best_idx] >= threshold:
        return known_names[best_idx]
    return "UNKNOWN"
