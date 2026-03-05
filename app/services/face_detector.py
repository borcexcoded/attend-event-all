import face_recognition


def detect_faces(image):
    """Detect face locations in an image."""
    return face_recognition.face_locations(image)
