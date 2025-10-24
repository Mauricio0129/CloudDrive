from fastapi import HTTPException

# noinspection SqlNoDataSourceInspection
class UserServices:

    def __init__(self, db):
        self.db = db

    async def check_if_user_exist_registration(self, username, email) -> None:
        """
        Verify that username and email are available during registration.
        Raises 409 conflict if either already exists.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", username, email)
            if row:
                raise HTTPException(status_code=409, detail="User already exists")

    async def get_user_id_password(self, identifier) -> dict:
        """
        Retrieve user ID and password for authentication.
        Accepts either username or email as identifier for flexible login.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT id, password FROM users WHERE username = $1 OR email = $1", identifier)
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_data = dict(row)
            user_data["id"] = str(user_data["id"])  # Convert UUID to string for JSON serialization
            return user_data

    async def register_user(self, username, email,  hashed_password) -> str:
        """Create new user account and return the user ID."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3) RETURNING id",
                                      username, email, hashed_password)
            return str(row["id"])