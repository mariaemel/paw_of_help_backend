import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def save_animal_image(media_dir: str, animal_id: int, file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported file extension. Allowed: .jpg, .jpeg, .png, .webp")

    relative_dir = Path("animals") / str(animal_id)
    absolute_dir = Path(media_dir) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    absolute_path = absolute_dir / filename

    with absolute_path.open("wb") as out_file:
        content = file.file.read()
        out_file.write(content)

    return str(relative_dir / filename).replace(os.sep, "/")
