from fastapi import HTTPException
from asyncpg.exceptions import UniqueViolationError
from ..helpers.file_utils import format_db_returning_objects


# noinspection SqlNoDataSourceInspection
class ShareServices:
    def __init__(self, db, file_services, folder_services):
        self.db = db
        self.file_services = file_services
        self.folder_services = folder_services

    async def share_file(self, user_id, share_info):
        """Share a file with another user."""

        # Verify file ownership
        filename = await self.file_services.verify_file_existence_ownership(user_id, share_info.file_id)
        if not filename:
            raise HTTPException(status_code=404, detail="File not found")

        async with self.db.acquire() as conn:
            # Get receiver user
            receiver = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1", share_info.username
            )

            if not receiver:
                raise HTTPException(
                    status_code=404, detail=f"User '{share_info.username}' not found"
                )

            # Prevent self-sharing
            receiver_id = str(receiver["id"])
            if receiver_id == user_id:
                raise HTTPException(
                    status_code=400, detail="Cannot share with yourself"
                )

            # Create share with permissions (same connection)
            try:
                async with conn.transaction():
                    share_record = await conn.fetchrow(
                        "INSERT INTO shares (user_id, shared_with, file_id) "
                        "VALUES ($1, $2, $3) RETURNING id",
                        user_id,
                        receiver_id,
                        share_info.file_id,
                    )

                    share_id = str(share_record["id"])

                    await conn.execute(
                        "INSERT INTO permissions (share_id, read, write, delete) "
                        "VALUES ($1, $2, $3, $4) RETURNING id",
                        share_id,
                        share_info.read,
                        share_info.write,
                        share_info.delete,
                    )

                return {"message": f"File {filename} successfully shared with user {share_info.username}"}

            except UniqueViolationError:
                raise HTTPException(status_code=409, detail="Already shared")


    async def share_folder(self, user_id, share_info):
        """Share a folder with another user."""
        response = await self.folder_services.verify_folder_existence_ownership(user_id, share_info.folder_id)

        if not response:
            raise HTTPException(status_code=404, detail="Folder not found")
        foldername = str(response["filename"])

        async with self.db.acquire() as conn:
            receiver = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1", share_info.username
            )

            if not receiver:
                raise HTTPException(
                    status_code=404, detail=f"User '{share_info.username}' not found"
                )

            receiver_id = str(receiver["id"])
            if receiver_id == user_id:
                raise HTTPException(
                    status_code=400, detail="Cannot share with yourself"
                )

            try:
                async with conn.transaction():
                    share_record = await conn.fetchrow(
                        "INSERT INTO shares (user_id, shared_with, folder_id) "
                        "VALUES ($1, $2, $3) RETURNING id",
                        user_id,
                        receiver_id,
                        share_info.folder_id,
                    )

                    share_id = str(share_record["id"])

                    await conn.execute(
                        "INSERT INTO permissions (share_id, read, write, delete) "
                        "VALUES ($1, $2, $3, $4) RETURNING id",
                        share_id,
                        share_info.read,
                        share_info.write,
                        share_info.delete,
                    )

                return {"message": f"folder {foldername} successfully shared with user {share_info.username}"}

            except UniqueViolationError:
                raise HTTPException(status_code=409, detail="Already shared")


    async def get_shared_with_me(self, user_id):
        # Get share records
        async with self.db.acquire() as conn:
            share_info = await conn.fetch(
                'SELECT shares.shared_at, '
                'permissions."delete", permissions."write", permissions."read",'
                'files.id, files.name, files.size_in_bytes, files.type, '
                'users.email '
                'FROM shares '
                'JOIN permissions ON permissions.share_id = shares.id '
                'JOIN files ON files.id = shares.file_id '
                'JOIN users ON users.id = files.owner_id '
                'WHERE shares.shared_with = $1 AND files.parent_folder_id IS NULL '
                'UNION ALL '
                'SELECT shares.shared_at, '
                'permissions."delete", permissions."write", permissions."read", '
                'folders.id, folders.name, NULL as size_in_bytes, NULL as type, '
                'users.email '
                'FROM shares '
                'JOIN permissions ON permissions.share_id = shares.id '
                'JOIN folders ON folders.id = shares.folder_id '
                'JOIN users ON users.id = folders.owner_id '
                'WHERE shares.shared_with = $1 AND folders.parent_folder_id IS NULL ',
                 user_id)
        data = [dict(record) for record in share_info]
        formated_data = format_db_returning_objects(data)
        return {"content": formated_data}
