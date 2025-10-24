import re
from .aws import AwsServices
from fastapi import HTTPException
from ..schemas.schemas import UploadFileInfo
from ..helpers.file_utils import format_db_returning_objects


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
        Verify folder ownership and existence.
        Returns folder name if found, False otherwise.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM folders WHERE owner_id = $1 AND id = $2",
                                      user_id, folder_id)
            if row:
                return str(row["name"])
            return False


    async def check_if_folder_exist_at_location(self, folder_name, parent_folder_id, owner_id)-> str | None:
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

    async def verify_file_and_generate_aws_presigned_url(self, file: UploadFileInfo, user_id) ->  dict:

        if "/" in file.file_name or "\\" in file.file_name:
            raise HTTPException(status_code=400, detail="Slashes are not allowed in file_name")

        if file.folder_id:
            if not await self.get_folder_for_user(user_id, file.folder_id):
                raise HTTPException(status_code=400, detail="Folder not found")

        if  not file.file_conflict:
            if await self.get_file_for_user(user_id, file.folder_id, file.file_name):
                raise HTTPException(status_code=409, detail="File already exists use FILE-CONFLICT parameter to solve")
            return AwsServices.generate_presigned_upload_url(file.folder_id, user_id, file.file_size_in_bytes,
                                                             file.file_name)

        if file.file_conflict == "Replace":
            return AwsServices.generate_presigned_upload_url(file.folder_id, user_id, file.file_size_in_bytes,
                                                             file.file_name)

        new_name = self.generate_unique_filename(file.file_name)
        attempts = 0
        max_attempts = 10  # Safety limit

        while await self.get_file_for_user(user_id, file.folder_id, new_name):
            attempts += 1
            if attempts >= max_attempts:
                raise HTTPException(status_code=400, detail="Unable to generate unique filename. Please rename your file.")
            new_name = self.generate_unique_filename(new_name)
        return AwsServices.generate_presigned_upload_url(file.folder_id, user_id, file.file_size_in_bytes, new_name)


    @staticmethod
    def generate_unique_filename(file_name):
        pattern = r"(\(\d+\))\.\w+"
        match = re.search(pattern, file_name)

        if match:
            uncut_name = match.group(1) ## (1).png
            cut_left_parenthesis = uncut_name.split("(", 1)[1] ## 1).png
            cut_right_parenthesis = cut_left_parenthesis.rsplit(")", 1)[0] ## 1
            number = int(cut_right_parenthesis) ## 1 -> int
            new_number = number + 1 ## 1+
            return file_name.replace(f"({number})", f"({new_number})")
        else:
            name, ext = file_name.rsplit('.', 1)
            return name + f" (1).{ext}"

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

        if await self.check_if_folder_exist_at_location(folder_name, parent_folder_id, owner_id):
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

    async def check_if_user_has_enough_space(self, user_id, size):
        """Verify user has sufficient storage space. Raises 403 if insufficient."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT available_storage_in_bytes FROM users WHERE id = $1",
                user_id
            )
        if size > row["available_storage_in_bytes"]:
            raise HTTPException(status_code=403, detail="User doesnt have enough space")