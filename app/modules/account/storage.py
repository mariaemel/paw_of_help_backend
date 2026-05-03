import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def save_profile_avatar(media_dir: str, user_id: int, kind: str, file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Недопустимый формат файла. Допустимо: .jpg, .jpeg, .png, .webp")

    relative_dir = Path("profiles") / kind / str(user_id)
    absolute_dir = Path(media_dir) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    absolute_path = absolute_dir / filename

    with absolute_path.open("wb") as out_file:
        out_file.write(file.file.read())

    return str(relative_dir / filename).replace(os.sep, "/")
