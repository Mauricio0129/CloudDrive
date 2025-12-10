from fastapi import HTTPException
from ..helpers.file_utils import format_db_returning_objects


# noinspection SqlNoDataSourceInspection
class FolderServices:
    def __init__(self, db):
        self.db = db

    async def verify_folder_existence_ownership(self, user_id, folder_id) -> str | bool:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM folders WHERE owner_id = $1 AND id = $2",
                user_id,
                folder_id,
            )
            if row:
                return str(row["name"])
            return False

    async def check_if_folder_name_in_use_at_location(
        self, user_id, folder_name, parent_folder_id=None
    ) -> str | bool:
        async with self.db.acquire() as conn:
            if parent_folder_id:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id = $2 AND owner_id = $3",
                    folder_name,
                    parent_folder_id,
                    user_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT name FROM folders WHERE name = $1 AND parent_folder_id IS NULL AND owner_id = $2",
                    folder_name,
                    user_id,
                )
            if row:
                return str(row["name"])
            return False

    async def register_folder(self, folder_name, parent_folder_id, user_id) -> str:
        """
        Create new folder after validating parent folder existence and uniqueness at location.
        Raises 404 if parent folder not found, 409 if folder already exists at location.
        """
        await self.verify_parent_folder_if_provided(user_id, parent_folder_id)

        if await self.check_if_folder_name_in_use_at_location(
            user_id, folder_name, parent_folder_id
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Folder '{folder_name}' already exists in this location",
            )

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO folders (name, parent_folder_id, owner_id)"
                "VALUES ($1, $2, $3) RETURNING name",
                folder_name,
                parent_folder_id,
                user_id,
            )
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
                    user_data = await conn.fetchrow(
                        "SELECT username, email, available_storage_in_bytes, "
                        "total_storage_in_bytes "
                        "FROM users WHERE id = $1",
                        user_id,
                    )

                    data = await conn.fetch(
                        "SELECT id, name, created_at, last_interaction, size_in_bytes, type "
                        "FROM files WHERE owner_id = $1 AND parent_folder_id IS NULL "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size, NULL as type "
                        "FROM folders WHERE owner_id = $1 AND parent_folder_id IS NULL "
                        f"ORDER BY {sort_by} {order}",
                        user_id,
                    )
                else:
                    await self.verify_parent_folder_if_provided(user_id, location)
                    data = await conn.fetch(
                        "SELECT id, name, created_at, last_interaction, size_in_bytes, type, parent_folder_id "
                        "FROM files WHERE owner_id = $1 AND parent_folder_id = $2 "
                        "UNION ALL "
                        "SELECT id, name, created_at, last_interaction, NULL as size_in_bytes, NULL as type, parent_folder_id "
                        "FROM folders WHERE owner_id = $1 and parent_folder_id = $2 "
                        f"ORDER BY {sort_by} {order}",
                        user_id,
                        location,
                    )

            if not location:
                user_dict = dict(user_data)
            folder_files_list_of_records = [
                dict(record) for record in data
            ]  # Convert records to dicts
            # Format UUIDs and datetimes to strings for Pydantic
            formated_folder_files_list_of_records = format_db_returning_objects(
                folder_files_list_of_records
            )

            if not location:
                return {
                    "user": user_dict,
                    "files_and_folders": formated_folder_files_list_of_records,
                }
            return {"files_and_folders": formated_folder_files_list_of_records}

    async def rename_folder(self, user_id, parent_folder_id, folder_id, new_name):
        """
        Rename a folder if owned by the user and the new name is not already taken in the same location.
        """
        if await self.verify_folder_existence_ownership(user_id, folder_id):
            if await self.check_if_folder_name_in_use_at_location(
                user_id, new_name, parent_folder_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Folder '{new_name}' already exists in this location",
                )

            async with self.db.acquire() as conn:
                await conn.execute(
                    "UPDATE folders SET name = $1 WHERE id = $2", new_name, folder_id
                )

            return {"message": f"Folder renamed to: '{new_name}' "}
        raise HTTPException(status_code=404, detail="Folder doesn't exist")

    async def verify_parent_folder_if_provided(self, user_id, parent_folder_id):
        if parent_folder_id:
            if not await self.verify_folder_existence_ownership(
                user_id, parent_folder_id
            ):
                raise HTTPException(status_code=400, detail="Folder not found")
