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
        """
        Checks if the file exists and is owned by the user.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND id = $2",
                                      user_id, file_id)
            if row:
                return str(row["name"])
            return False

    async def verify_folder_existence_ownership(self, user_id, folder_id) -> str | bool:
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

    async def file_name_taken(self, user_id, folder_id, file_name) -> str | bool:
        """
        Check if a filename is already used by the user in the specified folder.
        This is used when uploading or renaming to avoid duplicate filenames in the same folder.
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
            return False

    async def temp_log_file_to_be_verified(self, user_id, folder_id, file_name, size_in_bytes, file_type) -> str:
        """
        Create temporary file record before S3 upload for verification tracking.

        - Logs file metadata to reserve storage space (deducts from available_storage_in_bytes)
        - Returns file UUID to use as immutable S3 key (enables renames without breaking storage)
        - Lambda trigger will set confirmed_upload=TRUE when file arrives in S3
        - Unconfirmed files can be cleaned up later if upload fails
        """
        if folder_id:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO files (name, size_in_bytes, type, owner_id, folder_id) "
                    "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                    file_name, size_in_bytes, file_type, user_id, folder_id
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
        """Check if folder with given name exists at specified location for this user."""
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

    async def update_existing_file_for_replace(self, user_id, folder_id, file_name, size_in_bytes, file_type) -> str:
        """Update existing file metadata for replacement, returns file UUID"""
        async with self.db.acquire() as conn:
            if folder_id:
                row = await conn.fetchrow(
                    "UPDATE files SET size_in_bytes = $1, type = $2 "
                    "WHERE owner_id = $3 AND folder_id = $4 AND name = $5 RETURNING id",
                    size_in_bytes, file_type, user_id, folder_id, file_name)
            else:
                row = await conn.fetchrow(
                    "UPDATE files SET size_in_bytes = $1, type = $2 "
                    "WHERE owner_id = $3 AND folder_id IS NULL AND name = $4 RETURNING id",
                    size_in_bytes, file_type, user_id, file_name)

            return str(row["id"])

    async def verify_file_and_generate_aws_presigned_upload_url(self, file: UploadFileInfo, user_id) -> dict:
        """
        Validate file upload request and generate S3 presigned URL with conflict resolution.

        Handles three upload scenarios:
        1. New file (no conflict): Creates new file record and generates upload URL
        2. Replace existing: Updates existing file metadata, reuses UUID to overwrite S3 object
        3. Keep both: Generates unique filename (e.g., 'photo (1).png'), creates new record

        Process:
        - Validates user has sufficient storage space
        - Verifies folder ownership if specified
        - Checks for filename conflicts at target location
        - Creates/updates database record (confirmed_upload=FALSE)
        - Returns presigned URL using file UUID as immutable S3 key

        S3 Structure: files/{user_id}/{folder_id}/{file_uuid}
        Database stores display name separately from S3 key (enables renames without breaking storage)

        Args:
            file: Upload request containing filename, size, folder_id, and conflict resolution strategy
            user_id: Owner of the file

        Returns:
            dict: S3 presigned POST URL with upload fields

        Raises:
            HTTPException 403: Insufficient storage space
            HTTPException 400: Invalid folder or unable to generate unique filename
            HTTPException 409: File conflict detected without resolution strategy
        """
        await self.check_if_user_has_enough_space(user_id, file.file_size_in_bytes)
        ext = file.file_name.rsplit(".", 1)[1]

        if file.folder_id:
            if not await self.verify_folder_existence_ownership(user_id, file.folder_id):
                raise HTTPException(status_code=400, detail="Folder not found")

        if not file.file_conflict:
            if await self.file_name_taken(user_id, file.folder_id, file.file_name):
                raise HTTPException(status_code=409, detail="File already exists use FILE-CONFLICT parameter to solve")

            filename_for_s3 = await self.temp_log_file_to_be_verified(user_id, file.folder_id, file.file_name,
                                                                      file.file_size_in_bytes, ext)

            return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, filename_for_s3,
                                                             file.folder_id)

        if file.file_conflict == "Replace":
            filename_for_s3 = await self.update_existing_file_for_replace(user_id, file.folder_id, file.file_name,
                                                                          file.file_size_in_bytes, ext)

            return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, filename_for_s3,
                                                             file.folder_id)

        new_name = self.generate_unique_filename(file.file_name)
        attempts = 0
        max_attempts = 10

        while await self.file_name_taken(user_id, file.folder_id, new_name):
            attempts += 1
            if attempts >= max_attempts:
                raise HTTPException(status_code=400,
                                    detail="Unable to generate unique filename. Please rename your file.")
            new_name = self.generate_unique_filename(new_name)

        filename_for_s3 = await self.temp_log_file_to_be_verified(user_id, file.folder_id, new_name,
                                                                  file.file_size_in_bytes, ext)

        return AwsServices.generate_presigned_upload_url(user_id, file.file_size_in_bytes, filename_for_s3,
                                                         file.folder_id)

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

    async def check_if_user_has_enough_space(self, user_id, file_size_in_bytes):
        """Verify user has sufficient storage space. Raises 403 if insufficient."""
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

            return {"message": f"Folder renamed to '{new_name}'"}
        raise HTTPException(status_code=404, detail="Folder doesn't exist")

    async def get_file_metadata_for_download(self, file_id):
        """Get file name, type, and folder_id for download URL generation."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name, type, folder_id FROM files WHERE id = $1", file_id)
        return row["name"], row["type"], row["folder_id"]

    async def get_user_presigned_download_url(self, user_id, file_id):
        """
        Generate presigned download URL for user's file.
        Verifies ownership and returns URL with proper filename.
        Raises 404 if file doesn't exist or user doesn't own it.
        """
        if await self.verify_file_existence_ownership(user_id, file_id):
            name, file_type, folder_id = await self.get_file_metadata_for_download(file_id)
            return AwsServices.generate_presigned_download_url(user_id, file_id, name, file_type, folder_id)
        raise HTTPException(status_code=404, detail="File doesn't exist")
