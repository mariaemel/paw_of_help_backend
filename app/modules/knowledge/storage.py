import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.modules.account.storage import ALLOWED_IMAGE_EXTENSIONS

_COVER_MAX_BYTES = 5 * 1024 * 1024


def save_knowledge_cover(media_dir: str, article_id: int, file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Недопустимый формат файла. Допустимо: .jpg, .jpeg, .png, .webp")

    content = file.file.read()
    if len(content) > _COVER_MAX_BYTES:
        raise ValueError("Файл слишком большой. Максимум 5 МБ")

    relative_dir = Path("knowledge") / str(article_id)
    absolute_dir = Path(media_dir) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"cover_{uuid4().hex}{extension}"
    absolute_path = absolute_dir / filename
    with absolute_path.open("wb") as out_file:
        out_file.write(content)

    return str(relative_dir / filename).replace(os.sep, "/")
