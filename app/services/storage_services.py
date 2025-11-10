import re
from .aws import AwsServices
from fastapi import HTTPException
from ..schemas.schemas import UploadFileInfo
from ..helpers.file_utils import format_db_returning_objects


# noinspection SqlNoDataSourceInspection
class StorageServices:
    def __init__(self, db):
        self.db = db

    async def verify_file_existence_ownership(self, user_id, file_id):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND id = $2",
                                      user_id, file_id)
            if row:
                return str(row["name"])
            return False

    async def verify_folder_existence_ownership(self, user_id, folder_id) -> str | bool:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM folders WHERE owner_id = $1 AND id = $2",
                                      user_id, folder_id)
            if row:
                return str(row["name"])
            return False

    async def is_file_name_taken(self, user_id, file_name, parent_folder_id = None) -> str | bool:
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetch("SELECT name FROM files WHERE owner_id = $1 AND parent_folder_id = $2 AND name = $3",
                                          user_id, parent_folder_id, file_name)
            else:
                row = await conn.fetch("SELECT name FROM files WHERE owner_id = $1 AND parent_folder_id IS NULL AND name = $2",
                                          user_id, file_name)
            if row:
                already_used_names_at_location = [name for name in row["name"]]
            return False

    async def temp_log_file_to_be_verified(self, user_id, parent_folder_id, file_name, size_in_bytes, file_type) -> str:
        """
        Create temporary file record before S3 upload for verification tracking.

        - Logs file metadata to reserve storage space (deducts from available_storage_in_bytes)
        - Returns file UUID to use as immutable S3 key (enables renames without breaking storage)
        - Lambda trigger will set confirmed_upload=TRUE when file arrives in S3
        - Unconfirmed files can be cleaned up later if upload fails
        """
        if parent_folder_id:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO files (name, size_in_bytes, type, owner_id, parent_folder_id) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                    file_name, size_in_bytes, file_type, user_id, parent_folder_id
                )
        else:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO files (name, size_in_bytes, type, owner_id) "
                    "VALUES ($1, $2, $3, $4) RETURNING id",
                    file_name, size_in_bytes, file_type, user_id
                )

        return str(row["id"])

    async def check_if_folder_name_in_use_at_location(self, user_id, folder_name, parent_folder_id = None)-> str | bool:
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id = $2 AND owner_id = $3",
                    folder_name, parent_folder_id, user_id

                )
            else:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id IS NULL AND owner_id = $2",
                    folder_name, user_id
                )
            if row:
                return str(row["name"])
            return False

    async def get_existing_file_uuid_and_size(self, user_id, parent_folder_id, file_name) -> tuple[str, int] | None:
        """Update existing file metadata for replacement, returns file UUID"""
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow("SELECT id, size_in_bytes FROM files "
                                          "WHERE owner_id = $1 AND name = $2 AND parent_folder_id = $3 "
                                          , user_id, file_name, parent_folder_id)
            else:
                row = await conn.fetchrow("SELECT id, size_in_bytes FROM files WHERE owner_id = $1 AND name = $2 AND "
                                          "parent_folder_id IS NULL"
                                          , user_id, file_name)

            return (str(row["id"]), row["size_in_bytes"]) if row else None

    async def upload_an_new_file(self, file: UploadFileInfo, user_id)-> dict:
        await self.check_if_user_has_enough_space(user_id, file.file_size_in_bytes)
        ext = file.file_name.rsplit(".", 1)[1]

        if file.parent_folder_id:
            if not await self.verify_folder_existence_ownership(user_id, file.parent_folder_id):
                raise HTTPException(status_code=400, detail="Folder not found")

        if await self.is_file_name_taken(user_id, file.file_name, file.parent_folder_id):
            raise HTTPException(status_code=409, detail="File already exists use FILE-CONFLICT parameter to solve")
            ##this is actually the file id, but we do use it as the name of the file in s3
        name_s3_id = await self.temp_log_file_to_be_verified(user_id, file.parent_folder_id, file.file_name,
                                                                 file.file_size_in_bytes, ext)

        return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, name_s3_id,
                                                             file.parent_folder_id)

    async def replace_existing_file(self, file: UploadFileInfo, user_id) -> dict:
        if file.parent_folder_id:
            if not await self.verify_folder_existence_ownership(user_id, file.parent_folder_id):
                raise HTTPException(status_code=400, detail="Folder not found")

        existing = await self.get_existing_file_uuid_and_size(user_id, file.parent_folder_id, file.file_name)

        if not existing:
           raise HTTPException(status_code=404, detail="File not found")
        name_s3_id, bytes_size = existing

        if  file.file_size_in_bytes > bytes_size:
            size_difference = file.file_size_in_bytes - bytes_size
            await self.check_if_user_has_enough_space(user_id, size_difference)

        return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, name_s3_id,
                                                        file.parent_folder_id)

    async def keep_both_files(self, file: UploadFileInfo, user_id) -> dict:
        if file.parent_folder_id:
            if not await self.verify_folder_existence_ownership(user_id, file.parent_folder_id):
                raise HTTPException(status_code=400, detail="Folder not found")


        await self.check_if_user_has_enough_space(user_id, file.file_size_in_bytes)
        ext = file.file_name.rsplit(".", 1)[1]
        new_name = self.generate_unique_filename(file.file_name)

        attempts = 0
        max_attempts = 10

        while await self.is_file_name_taken(user_id, new_name, file.parent_folder_id):
            attempts += 1
            if attempts >= max_attempts:
                raise HTTPException(status_code=400,
                                    detail="Unable to generate unique filename. Please rename your file.")
            new_name = self.generate_unique_filename(new_name)

        s3_file_id = await self.temp_log_file_to_be_verified(user_id, file.parent_folder_id, new_name,
                                                             file.file_size_in_bytes, ext)

        return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, s3_file_id,
                                                         file.parent_folder_id)

    @staticmethod
    def generate_unique_filename(file_name):
        """
        Generate unique filename by incrementing number (e.g., 'photo (1).png' → 'photo (2).png').
        Matches last '(number)' before extension. If no match, adds ' (1)' before extension.
        """
        pattern = r"(\(\d+\))\.\w+"
        match = re.search(pattern, file_name)

        if match:
            uncut_name = match.group(1)
            cut_left_parenthesis = uncut_name.split("(", 1)[1]
            cut_right_parenthesis = cut_left_parenthesis.rsplit(")", 1)[0]
            number = int(cut_right_parenthesis)
            new_number = number + 1
            return file_name.replace(f"({number})", f"({new_number})")
        else:
            name, ext = file_name.rsplit('.', 1)
            return name + f"(1).{ext}"

    async def register_folder(self, folder_name, parent_folder_id, user_id) -> str:
        """
        Create new folder after validating parent folder existence and uniqueness at location.
        Raises 404 if parent folder not found, 409 if folder already exists at location.
        """
        if parent_folder_id:
            if not await self.verify_folder_existence_ownership(user_id, parent_folder_id):
                raise HTTPException(status_code=404, detail="Parent folder not found")

        if await self.check_if_folder_name_in_use_at_location(user_id, folder_name, parent_folder_id):
            raise HTTPException(status_code=409, detail=f"Folder '{folder_name}' already exists in this location")

        async with self.db.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO folders (name, parent_folder_id, owner_id)" 
                                      "VALUES ($1, $2, $3) RETURNING name", folder_name, parent_folder_id, user_id)
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
                        "SELECT id, name, created_at, last_interaction, size_in_bytes, type "
                        "FROM files WHERE owner_id = $1 AND parent_folder_id IS NULL "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size, NULL as type "
                        "FROM folders WHERE owner_id = $1 AND parent_folder_id IS NULL "
                        f"ORDER BY {sort_by} {order}", user_id
                    )
                else:
                    data = await conn.fetch(
                        "SELECT id, name, created_at, last_interaction, size_in_bytes, type, parent_folder_id "
                        "FROM files WHERE owner_id = $1 AND parent_folder_id = $2 "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size_in_bytes, NULL as type, parent_folder_id "
                        "FROM folders WHERE owner_id = $1 and parent_folder_id = $2 "
                        f"ORDER BY {sort_by} {order}", user_id, location
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

    async def check_if_user_has_enough_space(self, user_id, file_size_in_bytes):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT available_storage_in_bytes FROM users WHERE id = $1",
                user_id
            )
        if file_size_in_bytes > row["available_storage_in_bytes"]:
            raise HTTPException(status_code=403, detail="User doesnt have enough space")

    async def rename_folder(self, user_id, parent_folder_id, folder_id, new_name):
        """
        Rename a folder if owned by the user and the new name is not already taken in the same location.
        """
        if await self.verify_folder_existence_ownership(user_id, folder_id):
            if await self.check_if_folder_name_in_use_at_location(user_id, new_name, parent_folder_id):
                raise HTTPException(status_code=409, detail=f"Folder '{new_name}' already exists in this location")

            async with self.db.acquire() as conn:
                await conn.execute("UPDATE folders SET name = $1 WHERE id = $2", new_name, folder_id)

            return {"message": f"Folder renamed to: '{new_name}' "}
        raise HTTPException(status_code=404, detail="Folder doesn't exist")

    async def get_file_metadata_for_download(self, file_id):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name, parent_folder_id FROM files WHERE id = $1", file_id)
        return row["name"], row["parent_folder_id"]

    async def get_user_presigned_download_url(self, user_id, file_id):
        """
        Generate presigned download URL for user's file.
        Verifies ownership and returns URL with proper filename.
        Raises 404 if file doesn't exist or user doesn't own it.
        """
        if await self.verify_file_existence_ownership(user_id, file_id):
            name, folder_id = await self.get_file_metadata_for_download(file_id)
            return AwsServices.generate_presigned_download_url(user_id, file_id, name, folder_id)
        raise HTTPException(status_code=404, detail="File doesn't exist")

    async def rename_file(self, user_id, file_id, file_name, parent_folder_id):
        """
        Rename file after verifying ownership and checking for name conflicts.
        Verifies file ownership, checks if new name is taken at location, updates display name.
        Returns success message on completion.
        """
        if not await self.verify_file_existence_ownership(user_id, file_id):
            raise HTTPException(status_code=404, detail="File doesn't exist")
        if await self.is_file_name_taken(user_id, file_name, parent_folder_id):
            raise HTTPException(status_code=409, detail=f"File '{file_name}' already exists in this location")
        async with self.db.acquire() as conn:
            await conn.execute("UPDATE files SET name = $1 WHERE id = $2", file_name, file_id)
        return {"message": f"File renamed to '{file_name}'"}