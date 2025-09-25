from fastapi import UploadFile
from pathlib import Path
from fastapi import HTTPException
from itertools import chain
from dependencies import format_db_returning_objects

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

    async def register_file(self, file: UploadFile, user_id, folder_id) ->  str:
        path = Path(file.filename)
        name = path.stem
        ext = path.suffix.lstrip('.')

        if await self.get_file_for_user(user_id, folder_id, name):
            raise HTTPException(status_code=400, detail="File already exists use X-FILE-CONFLICT header to solve")

        if not await self.get_folder_for_user(user_id, folder_id):
            raise HTTPException(status_code=400, detail="Folder not found")

        size = await self.calculate_file_size(file)  ## calculate file size asynchronously
        size = self.format_file_size(size)  ## format file size(e.g, bytes to KB, MB)

        async with self.db.acquire() as conn:
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
    async def retrieve_folder_content(self, user_id, location = None):
        async with self.db.acquire() as conn:
            async with conn.transaction():
                if not location:
                    files = await conn.fetch("SELECT id, name, size, type, last_interaction "
                                             "FROM files WHERE owner_id = $1 AND folder_id IS NULL", user_id)

                    folders = await conn.fetch("SELECT id, name, last_interaction, parent_folder_id FROM folders "
                                            "WHERE owner_id = $1 and parent_folder_id IS NULL", user_id)
                else:
                    files = await conn.fetch("SELECT id, name, size, type, last_interaction "
                                             "FROM files WHERE owner_id = $1 AND folder_id = $2", user_id, location)

                    folders = await conn.fetch("SELECT id, name, last_interaction, parent_folder_id FROM folders "
                                              "WHERE owner_id = $1 and parent_folder_id = $2", user_id, location)

                file_list = [dict(files) for files in files]
                folder_list = [dict(folders) for folders in folders]
                combined = list(chain(file_list, folder_list))
                result = format_db_returning_objects(combined)
        return result