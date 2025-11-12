from app.services.storage_services import StorageServices
from fastapi import HTTPException
import pytest

@pytest.fixture(scope="session")
async def storage_services(db_pool):
    """Created once per session"""
    return StorageServices(db_pool)


async def test_register_folder_at_root_succeeds(storage_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent):
    """Test that creating a root-level folder succeeds when name is unique."""
    # Create user who will own the folder
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create folder at root
    folder_name = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         valid_folder_data_no_parent.parent_folder_id, user_id)

    # Verify folder was created with correct name
    assert folder_name == valid_folder_data_no_parent.folder_name


async def test_duplicate_folder_at_root_raises_409(storage_services, user_services, valid_user_data,
                                                   valid_folder_data_no_parent):
    """Test that creating a duplicate folder at root raises 409."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create folder first time - succeeds
    await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                           valid_folder_data_no_parent.parent_folder_id, user_id)

    # Try to create same folder again - should fail
    with pytest.raises(HTTPException) as exc_info:
        await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                               valid_folder_data_no_parent.parent_folder_id, user_id)

    assert exc_info.value.status_code == 409


async def test_register_folder_at_set_location_succeeds(storage_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent, db_pool):
    """Test that creating a nested folder succeeds when name is unique in that location."""
    # Create user who will own the folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create parent folder at root
    folder_name = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get parent folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        parent_folder_id = str(row["id"])

    # Create folder inside parent folder
    child_folder = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         parent_folder_id, user_id)

    assert child_folder == valid_folder_data_no_parent.folder_name


async def test_register_duplicate_folder_at_set_location_raises_409(storage_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent, db_pool):
    """Test that creating a duplicate nested folder raises 409."""
    # Create user who will own the folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create parent folder at root
    folder_name = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         valid_folder_data_no_parent.parent_folder_id, user_id)

    # Get parent folder ID
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM folders WHERE name = $1", folder_name)
        parent_folder_id = str(row["id"])

    # Create folder inside parent folder
    child_folder = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         parent_folder_id, user_id)

    # Try to create same folder again - should fail
    with pytest.raises(HTTPException) as exc_info:
        await storage_services.register_folder(valid_folder_data_no_parent.folder_name, parent_folder_id, user_id)

    assert exc_info.value.status_code == 409


async def test_retrieving_empty_user_content_works(storage_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent, db_pool):
    """Test that retrieving content for a user with no files or folders returns empty list."""
    # Create user with no folders
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    data = await storage_services.retrieve_folder_content(user_id,"last_interaction", "ASC")
    print(data)
    assert data["files_and_folders"] == []

async def test_retrieving_user_content_works(storage_services, valid_user_data, user_services,
                                                valid_folder_data_no_parent, db_pool):
    """Test that retrieving content for a user with folders returns correct data."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email,
                                                    valid_user_data.password)

    # Create folder at root
    folder_name = await storage_services.register_folder(valid_folder_data_no_parent.folder_name,
                                                         valid_folder_data_no_parent.parent_folder_id, user_id)

    data = await storage_services.retrieve_folder_content(user_id, "last_interaction", "ASC")
    print(data)
    assert data["files_and_folders"][0]["name"] == folder_name


async def test_retrieve_content_from_nonexistent_folder_raises_400(storage_services, valid_user_data, user_services, valid_folder_data_no_parent, db_pool):
    """Test that retrieving content from a non-existent folder raises 400."""
    # Create user
    user_id = await user_services.register_new_user(valid_user_data.username, valid_user_data.email, valid_user_data.password)

    # Try to retrieve content from fake folder UUID
    with pytest.raises(HTTPException) as exc_info:
        await storage_services.retrieve_folder_content(user_id, sort_by="last_interaction", order="ASC", location="e8d52a78-7140-4d03-afd8-d0bc43cf2c9b")

    assert exc_info.value.status_code == 400