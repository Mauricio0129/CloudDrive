from fastapi import UploadFile
from pathlib import Path
from fastapi import HTTPException
from app.dependencies import format_db_returning_objects

# noinspection SqlNoDataSourceInspection
class StorageServices:
    def __init__(self, db):
        self.db = db

    async def get_file_for_user(self, user_id, folder_id, file_name) -> str | None:
        """
        Verify file ownership by checking owner_id, folder_id, and filename.
        Returns filename if found, None otherwise.
        """
        async with self.db.acquire() as conn:
            if folder_id:
                row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id = $2 AND name = $3",
                                          user_id, folder_id, file_name)
            else:
                row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id IS NULL AND name = $2",
                                          user_id, file_name)
            if row:
                return str(row["name"])
            return None


    async def get_folder_for_user(self, user_id, folder_id) -> str | bool:
        """
        Verify folder ownership. Returns folder name if found, False if not found, True if no folder_id provided.
        """
        if folder_id:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow("SELECT name FROM folders WHERE owner_id = $1 AND id = $2"
                                          , user_id, folder_id,)
                if row:
                    return str(row["name"])
                return False
        return True

    @staticmethod
    async def calculate_file_size(file: UploadFile) -> int:
        """Calculate file size by reading in 1MB chunks. Resets file pointer to start when complete."""
        size = 0
        read_size = 1048576
        while True:
            chunk = await file.read(read_size)
            if not chunk:
                break
            size += len(chunk)
        await file.seek(0)
        return size

    @staticmethod
    def format_file_size(size: int) -> str:
        """Format bytes to human-readable string (B, KB, MB) using base-10 calculation."""
        if size >= 1000000:
            size = size // 1000000
            size = str(size) + "MB"
        elif size >= 1000:
            size = size // 1000
            size = str(size) + "KB"
        else:
            size = str(size) + "B"
        return size

    @staticmethod
    async def adjust_user_storage(user_id, file_size, conn):
        """
        Deduct file size from user's available storage.
        Raises 413 error if insufficient space available.
        """
        size_to_subtract_from_user_storage = file_size // 1024
        available = await conn.fetchval(
            "SELECT available_storage_kb FROM users WHERE id = $1", user_id
        )

        if available < size_to_subtract_from_user_storage:
            raise HTTPException(status_code=413, detail="Not enough storage space")

        update_storage = await conn.execute("UPDATE users SET available_storage_kb"
                                            " = available_storage_kb - $1 WHERE id = $2",
                                            size_to_subtract_from_user_storage, user_id)

    async def register_file(self, file: UploadFile, user_id, folder_id) ->  str:
        """
        Register new file in database after validation.
        Validates file uniqueness, folder existence, and available storage.
        """
        path = Path(file.filename)
        name = path.stem
        ext = path.suffix.lstrip('.')

        if await self.get_file_for_user(user_id, folder_id, name):
            raise HTTPException(status_code=400, detail="File already exists use X-FILE-CONFLICT header to solve")

        if not await self.get_folder_for_user(user_id, folder_id):
            raise HTTPException(status_code=400, detail="Folder not found")

        size = await self.calculate_file_size(file)
        size_in_bytes = size
        size = self.format_file_size(size)

        async with self.db.acquire() as conn:
            async with conn.transaction():
                await self.adjust_user_storage(user_id, size_in_bytes, conn)

                row = await conn.fetchrow(
                    "INSERT INTO files (name, size, type, owner_id, folder_id) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING name",
                    name, size, ext, user_id, folder_id)

        return str(row["name"])

    async def check_folder_exists_at_location(self, folder_name, parent_folder_id, owner_id)-> str | None:
        """Check if folder with given name exists at specified location for this user."""
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id = $2 AND owner_id = $3",
                    folder_name, parent_folder_id, owner_id

                )
            else:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id IS NULL AND owner_id = $2",
                    folder_name, owner_id
                )
            if row:
                return str(row["name"])
            return None

    async def validate_parent_folder(self, parent_folder_id, owner_id) -> bool | None:
        """Verify that parent folder exists and belongs to user."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM folders WHERE id = $1 AND owner_id = $2",
                parent_folder_id, owner_id
            )
            return bool(row)

    async def register_folder(self, folder_name, parent_folder_id, owner_id) -> str:
        """
        Create new folder after validating parent folder existence and uniqueness at location.
        Raises 404 if parent folder not found, 409 if folder already exists at location.
        """
        if parent_folder_id:
            if not await self.validate_parent_folder(parent_folder_id, owner_id):
                raise HTTPException(status_code=404, detail="Parent folder not found")

        if await self.check_folder_exists_at_location(folder_name, parent_folder_id, owner_id):
            raise HTTPException(status_code=409, detail=f"Folder '{folder_name}' already exists in this location")

        async with self.db.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO folders (name, parent_folder_id, owner_id)" 
                                      "VALUES ($1, $2, $3) RETURNING name", folder_name, parent_folder_id, owner_id)
            return str(row["name"])

    async def retrieve_folder_content(self, user_id, sort_by, order, location=None):
        """
        Retrieve files and folders at specified location (or root if None).
        Uses UNION query to merge and sort files/folders together.
        User info only included when retrieving root directory.
        """
        async with self.db.acquire() as conn:
            async with conn.transaction():

                if not location:
                    user_data = await conn.fetchrow("SELECT username, email, available_storage_in_bytes, "
                                                    "total_storage_in_bytes "
                                                    "FROM users WHERE id = $1", user_id)

                    data = await conn.fetch(
                        "SELECT id, name, created_at, last_interaction, size, type "
                        "FROM files WHERE owner_id = $1 AND folder_id IS NULL "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size, NULL as type "
                        "FROM folders WHERE owner_id = $1 AND parent_folder_id IS NULL "
                        f"ORDER BY {sort_by} {order}", user_id
                    )
                else:
                    data = await conn.fetch(
                        "SELECT id, name, created_at, last_interaction, size, type, NUll as parent_folder_id "
                        "FROM files WHERE owner_id = $1 AND folder_id = $2 "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size, NULL as type, parent_folder_id "
                        "FROM folders WHERE owner_id = $1 and parent_folder_id = $2 "
                        "ORDER BY {sort_by} {order}", user_id, location
                    )

            if not location:
                user_dict = dict(user_data)
            folder_files_list_of_records = [dict(record) for record in data]
            formated_folder_files_list_of_records = format_db_returning_objects(folder_files_list_of_records)

            if not location:
                return {
                    "user": user_dict,
                    "files_and_folders": formated_folder_files_list_of_records,
                }
            return {
                "files_and_folders": formated_folder_files_list_of_records
            }

    async def check_if_user_has_enough_space(self, user_id, size):
        """Verify user has sufficient storage space. Raises 403 if insufficient."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT available_storage_in_bytes FROM users WHERE id = $1",
                user_id
            )
        if size > row["available_storage_in_bytes"]:
            raise HTTPException(status_code=403, detail="User doesnt have enough space")