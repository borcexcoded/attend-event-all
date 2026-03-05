import numpy as np
import face_recognition


def match_face(known_encodings, known_names, unknown_encoding, tolerance=0.5):
    """Match an unknown face encoding against known encodings."""
    matches = face_recognition.compare_faces(
        known_encodings, unknown_encoding, tolerance=tolerance
    )
    if True in matches:
        index = matches.index(True)
        return known_names[index]
    return "UNKNOWN"
