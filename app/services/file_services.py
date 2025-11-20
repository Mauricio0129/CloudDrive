import re
from ..schemas.schemas import UploadFileInfo
from fastapi import HTTPException
from .aws import AwsServices
from ..helpers.file_utils import allowed_extensions


class FileServices:
    def __init__(self, db, folder_services):
        self.db = db
        self.folder_services = folder_services

    async def verify_file_existence_ownership(self, user_id, file_id):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM files WHERE owner_id = $1 AND id = $2",
                user_id,
                file_id,
            )
            if row:
                return str(row["name"])
            return False

    async def is_file_name_taken(
        self, user_id, file_name, parent_folder_id=None
    ) -> bool:
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow(
                    "SELECT name FROM files WHERE owner_id = $1 AND parent_folder_id = $2 AND name = $3",
                    user_id,
                    parent_folder_id,
                    file_name,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT name FROM files WHERE owner_id = $1 AND parent_folder_id IS NULL AND name = $2",
                    user_id,
                    file_name,
                )
            return row is not None

    async def temp_log_file_to_be_verified(
        self, user_id, parent_folder_id, file_name, size_in_bytes, file_type
    ) -> str:
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
                    file_name,
                    size_in_bytes,
                    file_type,
                    user_id,
                    parent_folder_id,
                )
        else:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "INSERT INTO files (name, size_in_bytes, type, owner_id) "
                    "VALUES ($1, $2, $3, $4) RETURNING id",
                    file_name,
                    size_in_bytes,
                    file_type,
                    user_id,
                )

        return str(row["id"])

    async def get_existing_file_uuid_and_size(
        self, user_id, parent_folder_id, file_name
    ) -> tuple[str, int] | None:
        """Update existing file metadata for replacement, returns file UUID"""
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow(
                    "SELECT id, size_in_bytes FROM files "
                    "WHERE owner_id = $1 AND name = $2 AND parent_folder_id = $3 ",
                    user_id,
                    file_name,
                    parent_folder_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT id, size_in_bytes FROM files WHERE owner_id = $1 AND name = $2 AND "
                    "parent_folder_id IS NULL",
                    user_id,
                    file_name,
                )

            return (str(row["id"]), row["size_in_bytes"]) if row else None

    async def upload_an_new_file(self, file: UploadFileInfo, user_id) -> dict:
        await self.check_if_user_has_enough_space(user_id, file.file_size_in_bytes)
        ext = file.file_name.rsplit(".", 1)[1]

        await self.folder_services.verify_parent_folder_if_provided(
            user_id, file.parent_folder_id
        )

        if await self.is_file_name_taken(
            user_id, file.file_name, file.parent_folder_id
        ):
            raise HTTPException(
                status_code=409,
                detail="File already exists use FILE-CONFLICT parameter to solve",
            )
            ##this is actually the file id, but we do use it as the name of the file in s3
        name_s3_id = await self.temp_log_file_to_be_verified(
            user_id, file.parent_folder_id, file.file_name, file.file_size_in_bytes, ext
        )

        return AwsServices.generate_presigned_upload_url(
            user_id, file.file_size_in_bytes, name_s3_id, file.parent_folder_id
        )

    async def replace_existing_file(self, file: UploadFileInfo, user_id) -> dict:
        await self.folder_services.verify_parent_folder_if_provided(
            user_id, file.parent_folder_id
        )

        existing = await self.get_existing_file_uuid_and_size(
            user_id, file.parent_folder_id, file.file_name
        )

        if not existing:
            raise HTTPException(status_code=404, detail="File not found")
        name_s3_id, bytes_size = existing

        if file.file_size_in_bytes > bytes_size:
            size_difference = file.file_size_in_bytes - bytes_size
            await self.check_if_user_has_enough_space(user_id, size_difference)

        return AwsServices.generate_presigned_upload_url(
            user_id, file.file_size_in_bytes, name_s3_id, file.parent_folder_id
        )

    async def keep_both_files(self, file: UploadFileInfo, user_id) -> dict:
        await self.folder_services.verify_parent_folder_if_provided(
            user_id, file.parent_folder_id
        )

        await self.check_if_user_has_enough_space(user_id, file.file_size_in_bytes)
        ext = file.file_name.rsplit(".", 1)[1]
        new_name = self.generate_unique_filename(file.file_name)

        attempts = 0
        max_attempts = 10

        while await self.is_file_name_taken(user_id, new_name, file.parent_folder_id):
            attempts += 1
            if attempts >= max_attempts:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to generate unique filename. Please rename your file.",
                )
            new_name = self.generate_unique_filename(new_name)

        s3_file_id = await self.temp_log_file_to_be_verified(
            user_id, file.parent_folder_id, new_name, file.file_size_in_bytes, ext
        )

        return AwsServices.generate_presigned_upload_url(
            user_id, file.file_size_in_bytes, s3_file_id, file.parent_folder_id
        )

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
            name, ext = file_name.rsplit(".", 1)
            return name + f"(1).{ext}"

    async def check_if_user_has_enough_space(self, user_id, file_size_in_bytes):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT available_storage_in_bytes FROM users WHERE id = $1", user_id
            )
        if file_size_in_bytes > row["available_storage_in_bytes"]:
            raise HTTPException(status_code=403, detail="User doesnt have enough space")

    async def get_file_metadata_for_download(self, file_id):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name, parent_folder_id FROM files WHERE id = $1", file_id
            )
        return row["name"], row["parent_folder_id"]

    async def get_user_presigned_download_url(self, user_id, file_id):
        """
        Generate presigned download URL for user's file.
        Verifies ownership and returns URL with proper filename.
        Raises 404 if file doesn't exist or user doesn't own it.
        """
        if await self.verify_file_existence_ownership(user_id, file_id):
            name, folder_id = await self.get_file_metadata_for_download(file_id)
            return AwsServices.generate_presigned_download_url(
                user_id, file_id, name, folder_id
            )
        raise HTTPException(status_code=404, detail="File doesn't exist")

    @staticmethod
    async def verify_extension_is_not_being_overwritten(file_name):
        # Check if there's a dot at all
        if "." not in file_name:
            return False

        name , ext = file_name.rsplit(".", 1)

        # Check if extension is empty (file ends with dot)
        if not ext:
            return False  # Empty extension safe

        if ext.lower() in allowed_extensions:
            return True

        return False ## Part of the filename safe

    async def rename_file(self, user_id, file_id, file_name, parent_folder_id):
        """
        Rename file after verifying ownership and checking for name conflicts.
        Verifies file ownership, checks if new name is taken at location, updates display name.
        Returns success message on completion.
        """

        # 1. Reject if user included extension
        if await self.verify_extension_is_not_being_overwritten(file_name):
            raise HTTPException(
                status_code=400,
                detail="Do not include file extension. Extension will be preserved automatically."
            )

        # 2. Verify ownership and get original filename
        old_name = await self.verify_file_existence_ownership(user_id, file_id)
        if not old_name:
            raise HTTPException(status_code=404, detail="File not found")

        # 3. Extract and preserve original extension
        _, ext = old_name.rsplit(".", 1)  # No check needed - all files have extensions ✅
        adjusted_name = f"{file_name}.{ext}"

        # 4. Check for naming conflicts
        if await self.is_file_name_taken(user_id, adjusted_name, parent_folder_id):
            raise HTTPException(
                status_code=409,
                detail=f"File '{adjusted_name}' already exists in this location"
            )

        # 5. Update filename
        async with self.db.acquire() as conn:
            await conn.execute(
                "UPDATE files SET name = $1 WHERE id = $2",
                adjusted_name,
                file_id
            )

        return {"message": f"File renamed to '{adjusted_name}'"}