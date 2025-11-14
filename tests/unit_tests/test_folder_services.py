from app.schemas.schemas import RegisterUser
from fastapi import HTTPException
import pytest

async def test_register_folder_at_root_succeeds(folder_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent):
    """Test that creating a root-level folder succeeds when name is unique."""
    # Create user who will own the folder
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)
    # Verify folder was created with correct name
    assert folder_name == valid_folder_data_no_parent.folder_name

async def test_duplicate_folder_at_root_raises_409(folder_services, user_services, valid_user_data,
                                                   valid_folder_data_no_parent):
    """Test that creating a duplicate folder at root raises 409."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create folder first time - succeeds
    await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                          valid_folder_data_no_parent.parent_folder_id, user_id)
    # Try to create same folder again - should fail
    with pytest.raises(HTTPException) as exc_info:
        await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                              valid_folder_data_no_parent.parent_folder_id, user_id)

    assert exc_info.value.status_code == 409

async def test_register_folder_at_set_location_succeeds(folder_services, valid_user_data, user_services,
                                                        valid_folder_data_no_parent, db_pool):
    """Test that creating a nested folder succeeds when name is unique in that location."""
    # Create user who will own the folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create parent folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)
    # Get parent folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        parent_folder_id = str(row["id"])

    # Create folder inside parent folder
    child_folder = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         parent_folder_id, user_id)

    assert child_folder == valid_folder_data_no_parent.folder_name

async def test_register_duplicate_folder_at_set_location_raises_409(folder_services, valid_user_data, user_services,
                                                                    valid_folder_data_no_parent, db_pool):
    """Test that creating a duplicate nested folder raises 409."""
    # Create user who will own the folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create parent folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)
    # Get parent folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        parent_folder_id = str(row["id"])

    # Create folder inside parent folder
    child_folder = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         parent_folder_id, user_id)

    # Try to create same folder again - should fail
    with pytest.raises(HTTPException) as exc_info:
        await folder_services.register_folder(valid_folder_data_no_parent.folder_name, parent_folder_id, user_id)

    assert exc_info.value.status_code == 409

async def test_retrieving_empty_user_content_works(folder_services, valid_user_data, user_services,
                                                   valid_folder_data_no_parent, db_pool):
    """Test that retrieving content for a user with no files or folders returns empty list."""
    # Create user with no folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    data = await folder_services.retrieve_folder_content(user_id, "last_interaction", "ASC")
    print(data)
    assert data["files_and_folders"] == []

async def test_retrieving_user_content_works(folder_services, valid_user_data, user_services,
                                             valid_folder_data_no_parent, db_pool):
    """Test that retrieving content for a user with folders returns correct data."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)

    data = await folder_services.retrieve_folder_content(user_id, "last_interaction", "ASC")
    print(data)
    assert data["files_and_folders"][0]["name"] == folder_name

async def test_retrieve_content_from_nonexistent_folder_raises_400(folder_services, valid_user_data, user_services,
                                                                   valid_folder_data_no_parent, db_pool):
    """Test that retrieving content from a non-existent folder raises 400."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Try to retrieve content from fake folder UUID
    with pytest.raises(HTTPException) as exc_info:
        await folder_services.retrieve_folder_content(user_id, sort_by="last_interaction", order="ASC",
                                                      location="e8d52a78-7140-4d03-afd8-d0bc43cf2c9b")

    assert exc_info.value.status_code == 400

async def test_retrieve_content_from_folder_works(folder_services, valid_user_data, user_services,
                                                  valid_folder_data_no_parent, db_pool):
    """Test that retrieving content from a non-existent folder raises 400."""
    # Create user who will own the folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create parent folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)
    # Get parent folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        parent_folder_id = str(row["id"])

    # Create folder inside parent folder
    child_folder = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         parent_folder_id, user_id)

    data = await folder_services.retrieve_folder_content(user_id, sort_by="last_interaction", order="ASC",
                                                         location=parent_folder_id)
    assert data["files_and_folders"][0]["name"] == folder_name

async def test_rename_folder_at_root_succeeds(folder_services, valid_user_data, user_services,
                                              valid_folder_data_no_parent, db_pool):
    """Test that renaming a folder succeeds when new name is available at that location."""
    # Create user who will own the folder
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get the newly created folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        folder_id = str(row["id"])

    # Rename folder
    await folder_services.rename_folder(user_id, None, folder_id, "test_folder_updated")

    # Verify folder was renamed in database
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT name FROM folders WHERE id = $1", folder_id)

    assert row["name"] == "test_folder_updated"

async def test_rename_folder_at_root_fails_when_name_at_use_at_location(folder_services, valid_user_data, user_services,
                                                                        valid_folder_data_no_parent, db_pool):
    """Test that renaming a folder fails when new name isn't available at that location."""
    # Create user who will own the folder
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)
    # Create folder at root
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get the newly created folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        folder_id = str(row["id"])

    with pytest.raises(HTTPException) as exc_info:
        await folder_services.rename_folder(user_id, None, folder_id,
                                            valid_folder_data_no_parent.folder_name)
    assert exc_info.value.status_code == 409

async def test_rename_unexisting_folder_raises_404(folder_services, valid_user_data, user_services,
                                                   valid_folder_data_no_parent, db_pool):
    """Test that renaming a folder fails when updating a none existing folder."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    with pytest.raises(HTTPException) as exc_info:
        await folder_services.rename_folder(user_id, None, "e8d52a78-7140-4d03-afd8-d0bc43cf2c9b",
                                             "test_folder_updated")
    assert exc_info.value.status_code == 404

async def test_verify_folder_ownership_returns_name_for_owner(folder_services, valid_user_data, user_services, valid_folder_data_no_parent, db_pool):
    """Test that verifying folder ownership returns folder name when user owns the folder."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email, valid_user_data.password)

    # Create folder owned by user
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name, valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        folder_id = str(row["id"])

    # Verify ownership check succeeds and returns folder name
    result = await folder_services.verify_folder_existence_ownership(user_id, folder_id)

    assert result == valid_folder_data_no_parent.folder_name

async def test_verify_folder_ownership_returns_false_for_wrong_user(folder_services, valid_user_data, user_services,
                                                                    valid_folder_data_no_parent, db_pool):
    """Test that verifying folder ownership returns False when folder belongs to different user."""
    # Create first user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create second user
    second_user = RegisterUser(username="test_user2", email="test2@test.com", password="test_password2")
    second_user_id = await user_services.register_new_user(second_user.username, second_user.email,
                                                           second_user.password)

    # Create folder owned by first user
    folder_name = await folder_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                        valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        folder_id = str(row["id"])

    # Verify ownership check fails for second user
    result = await folder_services.verify_folder_existence_ownership(second_user_id, folder_id)

    assert result == False