from fastapi import UploadFile
from pathlib import Path

# noinspection SqlNoDataSourceInspection
class StorageServices:
    def __init__(self, db):
        self.db = db

    async def check_if_file_exist_for_user_at_location(self, user_id, folder_id, file_name) -> str:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id = $2 AND name = $3"
                                      , user_id, folder_id, file_name)
            return str(row)

    @staticmethod
    async def calculate_file_size(file: UploadFile) -> int:
        size = 0
        read_size = 1048576
        while True:
            chunk = await file.read(read_size)
            if not chunk:
                break
            size += len(chunk)
        return size

    @staticmethod
    def format_file_size(size: int) -> str:
        if size >= 1000000:
            size = size // 1000000
            size = str(size) + "MB"
        elif size >= 1000:
            size = size // 1000
            size = str(size) + "KB"
        else:
            size = str(size) + "B"
        return size

    async def register_file(self, file: UploadFile, user_id, folder_id) -> bool:
        size = await self.calculate_file_size(file)  ## calculate file size asynchronously
        path = Path(file.filename)
        name = path.stem
        ext = path.suffix.lstrip('.')
        size = self.format_file_size(size)  ## format file size(e.g, bytes to KB, MB)

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO files (name, size, type, owner_id, folder_id) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                name, size, ext, user_id, folder_id)
        return bool(row)