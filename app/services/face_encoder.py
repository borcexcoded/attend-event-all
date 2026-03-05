import face_recognition


def encode_face(image, face_locations):
    """Encode faces found at given locations."""
    return face_recognition.face_encodings(image, face_locations)
