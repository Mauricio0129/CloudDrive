from fastapi import HTTPException
from pydantic import SecretStr


# noinspection SqlNoDataSourceInspection
class UserServices:

    def __init__(self, db, auth_services):
        self.db = db
        self.auth_services = auth_services

    async def get_user_id_and_password(self, identifier) -> dict:
        """
        Retrieve user ID and password for authentication.
        Accepts either username or email as identifier for flexible login.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, password FROM users WHERE username = $1 OR email = $1",
                identifier,
            )
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_data = dict(row)
            user_data["id"] = str(
                user_data["id"]
            )  # Convert UUID to string for JSON serialization
            return user_data

    async def register_new_user(
        self, username: str, email: str, password: SecretStr
    ) -> str:
        """
        Complete user registration flow: verify availability, hash password, create user.
        Returns the new user's ID.
        """
        async with self.db.acquire() as conn:
            # Check if username or email already exists
            existing = await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1 OR email = $2", username, email
            )
            if existing:
                raise HTTPException(
                    status_code=409, detail="credentials already in use"
                )

            # Hash password
            hashed_password = self.auth_services.hash_password(
                password.get_secret_value()
            )

            # Create user
            row = await conn.fetchrow(
                "INSERT INTO users (username, email, password) VALUES ($1, $2, $3) RETURNING id",
                username,
                email,
                hashed_password,
            )

            return str(row["id"])  # Return user ID, let route handle response
