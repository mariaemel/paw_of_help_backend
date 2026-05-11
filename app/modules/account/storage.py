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


def save_org_asset(
    media_dir: str,
    organization_id: int,
    kind: str,
    file: UploadFile,
    max_size_bytes: int,
) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Недопустимый формат файла. Допустимо: .jpg, .jpeg, .png, .webp")
    content = file.file.read()
    if len(content) > max_size_bytes:
        raise ValueError(f"Файл слишком большой. Максимум {max_size_bytes // (1024 * 1024)} МБ")

    relative_dir = Path("organizations") / str(organization_id) / kind
    absolute_dir = Path(media_dir) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    absolute_path = absolute_dir / filename
    with absolute_path.open("wb") as out_file:
        out_file.write(content)
    return str(relative_dir / filename).replace(os.sep, "/")


def save_org_chat_message_photo(
    media_dir: str,
    organization_id: int,
    dialog_id: int,
    file: UploadFile,
    max_size_bytes: int = 5 * 1024 * 1024,
) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Недопустимый формат файла. Допустимо: .jpg, .jpeg, .png, .webp")
    content = file.file.read()
    if len(content) > max_size_bytes:
        raise ValueError(f"Файл слишком большой. Максимум {max_size_bytes // (1024 * 1024)} МБ")

    relative_dir = Path("organizations") / str(organization_id) / "chat" / str(dialog_id)
    absolute_dir = Path(media_dir) / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    absolute_path = absolute_dir / filename
    with absolute_path.open("wb") as out_file:
        out_file.write(content)
    return str(relative_dir / filename).replace(os.sep, "/")
