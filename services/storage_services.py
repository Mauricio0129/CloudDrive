from fastapi import UploadFile
from pathlib import Path

# noinspection SqlNoDataSourceInspection
class StorageServices:
    def __init__(self, db):
        self.db = db

## we have to compare with the 3 params to be 100% sure the file is actually a users file
## this is because more than 1 user could have files at root so using the 3 params guarantees 100% accuracy to determine
## if the user is the actual owner
    async def file_exists_for_user(self, user_id, folder_id, file_name) -> str | None:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id = $2 AND name = $3"
                                      , user_id, folder_id, file_name)
            if row:
                return str(row["name"])##we return string of the file name to later implement duplicates logic
            return None

    @staticmethod
    async def calculate_file_size(file: UploadFile) -> int:
        size = 0
        read_size = 1048576
        while True:
            chunk = await file.read(read_size)
            if not chunk:
                break
            size += len(chunk)
        await file.seek(0) ##we reset the position at the beginning of the file for any subsequent operations
        return size

## In web context we use base of 10 logic to calculate size, and they show sizes in whole numbers not decimals
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