import face_recognition
import numpy as np
import ast

def encode_wajah(file_stream):
    """Ambil encoding wajah dari file upload"""
    image = face_recognition.load_image_file(file_stream)
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return None
    return encodings[0]

def bandingkan_wajah(encoding_db, encoding_upload, tolerance=0.5):
    """Bandingkan wajah upload dengan wajah dari database"""
    if isinstance(encoding_db, str):  # kalau dari DB string
        encoding_db = np.array(ast.literal_eval(encoding_db))
    return face_recognition.compare_faces([encoding_db], encoding_upload, tolerance)[0]
