from fastapi import UploadFile
from pathlib import Path
from fastapi import HTTPException
from app.dependencies import format_db_returning_objects

# noinspection SqlNoDataSourceInspection
class StorageServices:
    def __init__(self, db):
        self.db = db

## we have to compare with the 3 params to be 100% sure the file is actually a users file
## this is because more than 1 user could have files at root so using the 3 params guarantees 100% accuracy to determine
## if the user is the actual owner
    async def get_file_for_user(self, user_id, folder_id, file_name) -> str | None:
        async with self.db.acquire() as conn:
            if folder_id:
                row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id = $2 AND name = $3",
                                          user_id, folder_id, file_name)
            else:
                row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id IS NULL AND name = $2",
                                          user_id, file_name)
            if row:
                return str(row["name"])  ## we return string of the file name to later implement duplicates logic
            return None


    async def get_folder_for_user(self, user_id, folder_id) -> str | bool:
        if folder_id:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow("SELECT name FROM folders WHERE owner_id = $1 AND id = $2"
                                          , user_id, folder_id,)
                if row:
                    return str(row["name"])##we return string of the file name to later implement duplicates logic
                return False
        return True

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

    @staticmethod
    async def adjust_user_storage(user_id, file_size, conn):
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
        path = Path(file.filename)
        name = path.stem
        ext = path.suffix.lstrip('.')

        if await self.get_file_for_user(user_id, folder_id, name):
            raise HTTPException(status_code=400, detail="File already exists use X-FILE-CONFLICT header to solve")

        if not await self.get_folder_for_user(user_id, folder_id):
            raise HTTPException(status_code=400, detail="Folder not found")

        size = await self.calculate_file_size(file)  ## calculate file size asynchronously
        size_in_bytes = size
        size = self.format_file_size(size)  ## format file size(e.g, bytes to KB, MB)

        async with self.db.acquire() as conn:
            async with conn.transaction():

                await self.adjust_user_storage(user_id, size_in_bytes, conn)

                row = await conn.fetchrow(
                    "INSERT INTO files (name, size, type, owner_id, folder_id) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING name",
                    name, size, ext, user_id, folder_id)

        return str(row["name"])

    async def check_folder_exists_at_location(self, folder_name, parent_folder_id, owner_id)-> str | None:
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
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM folders WHERE id = $1 AND owner_id = $2",
                parent_folder_id, owner_id
            )
            return bool(row)

    async def register_folder(self, folder_name, parent_folder_id, owner_id) -> str:
        if parent_folder_id: ## If we got passed a parent_folder_id we validate its existence
            if not await self.validate_parent_folder(parent_folder_id, owner_id):
                raise HTTPException(status_code=404, detail="Parent folder not found")

        ## Now we validate if the folder doesn't exist
        if await self.check_folder_exists_at_location(folder_name, parent_folder_id, owner_id):
            raise HTTPException(status_code=409, detail=f"Folder '{folder_name}' already exists in this location")

        ## If both conditions are meet meaning the parent folder exist or is null meaning is a root folder
        ## And the folder doesn't already exist at this location we register it
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO folders (name, parent_folder_id, owner_id)" 
                                      "VALUES ($1, $2, $3) RETURNING name", folder_name, parent_folder_id, owner_id)
            return str(row["name"])

    ## im calling the parameter location though technically is the parent_folder id but since its note called like that
    ## for the file bc for the file would be the folder_id it belongs to, but it also marks location for it, I decided to
    ## call it location and since the default entry root doest in
    async def retrieve_folder_content(self, user_id, sort_by, order, location=None):
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
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT available_storage_in_bytes FROM users WHERE id = $1",
                user_id
            )
        if size > row["available_storage_in_bytes"]:
            raise HTTPException(status_code=403, detail="User doesnt have enough space")