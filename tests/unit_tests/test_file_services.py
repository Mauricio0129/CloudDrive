from app.services.file_services import FileServices
from fastapi import HTTPException
from app.schemas.schemas import UploadFileInfo, RegisterUser
from unittest.mock import patch
import pytest


@pytest.fixture(scope="session")
def file_service(db_pool, folder_services):
    """Create FileServices instance for testing."""
    return FileServices(db_pool, folder_services)


@pytest.fixture
def valid_file_upload():
    """Standard file upload request with 230 bytes."""
    return UploadFileInfo(
        file_name="photo.png",
        file_size_in_bytes=230,
    )


@pytest.fixture
def valid_file_upload2():
    """Standard file upload request with 300 bytes."""
    return UploadFileInfo(
        file_name="vacation.jpg",
        file_size_in_bytes=300,
    )


@pytest.fixture
def larger_file_upload():
    """Larger file upload request with 320 bytes for replacement testing."""
    return UploadFileInfo(
        file_name="photo.png",
        file_size_in_bytes=320,
    )


@pytest.fixture
def mock_s3_response():
    """Mock S3 presigned upload URL response with fields for POST upload."""
    return {
        "url": "https://mock-bucket.s3.amazonaws.com/",
        "fields": {
            "key": "files/user-id/file-id",
            "AWSAccessKeyId": "MOCK_KEY",
            "policy": "mock_policy",
            "signature": "mock_signature",
        },
    }


@pytest.fixture
def mock_s3_download_response():
    """Mock S3 presigned download URL string."""
    return (
        "https://clouddriveproject.s3.amazonaws.com/files/"
        "9c917b9e-be19-40b9-a2ea-11e3c74188b0/bf64e556-820b-40b8-8ff4-bf0dd0a49e95?"
        "response-content-disposition=attachment%3B%20filename%3D%22photo.png%22"
        "&AWSAccessKeyId=AKIAXI7H6ZX36JI6NZFV&Signature=9ta85HeNiQPUpSNV%2BfMNaSx92eg%3D&Expires=1763091674"
    )


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_upload_new_file_returns_presigned_url(
        mock_aws,
        file_service,
        valid_file_upload,
        user_services,
        valid_user_data,
        mock_s3_response,
):
    """Test that uploading a new file with unique name returns S3 presigned URL."""
    mock_aws.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    response = await file_service.upload_an_new_file(valid_file_upload, user_id)

    assert response["url"] is not None
    mock_aws.assert_called_once()


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_upload_duplicate_file_raises_conflict_error(
        mock_aws,
        file_service,
        valid_file_upload,
        user_services,
        valid_user_data,
        mock_s3_response,
):
    """Test that uploading a file with duplicate name raises 409 conflict error."""
    mock_aws.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    await file_service.upload_an_new_file(valid_file_upload, user_id)

    with pytest.raises(HTTPException) as exc_info:
        await file_service.upload_an_new_file(valid_file_upload, user_id)

    assert exc_info.value.status_code == 409


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_replace_existing_file_returns_presigned_url(
        mock_aws,
        file_service,
        valid_file_upload,
        larger_file_upload,
        user_services,
        valid_user_data,
        mock_s3_response,
):
    """Test that replacing an existing file returns presigned URL for new upload."""
    mock_aws.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    await file_service.upload_an_new_file(valid_file_upload, user_id)

    response = await file_service.replace_existing_file(larger_file_upload, user_id)

    assert response["url"] is not None


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
@patch("app.services.file_services.AwsServices.generate_presigned_download_url")
async def test_get_file_returns_download_url_for_owned_file(
        mock_download,
        mock_upload,
        file_service,
        valid_file_upload,
        user_services,
        valid_user_data,
        db_pool,
        mock_s3_download_response,
        mock_s3_response,
):
    """Test that getting an owned file returns presigned download URL."""
    mock_upload.return_value = mock_s3_response
    mock_download.return_value = mock_s3_download_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    await file_service.upload_an_new_file(valid_file_upload, user_id)

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM files WHERE name = $1", valid_file_upload.file_name
        )
        file_id = str(result["id"])

    response = await file_service.get_user_presigned_download_url(user_id, file_id)

    assert response is not None
    assert response.startswith("https://")


async def test_get_nonexistent_file_raises_not_found_error(
        file_service, user_services, valid_user_data
):
    """Test that getting a nonexistent file raises 404 not found error."""
    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    file_id = "e8d52a78-7140-4d03-afd8-d0bc43cf2c9b"

    with pytest.raises(HTTPException) as exc_info:
        await file_service.get_user_presigned_download_url(user_id, file_id)

    assert exc_info.value.status_code == 404


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
@patch("app.services.file_services.AwsServices.generate_presigned_download_url")
async def test_get_file_owned_by_other_user_raises_not_found_error(
        mock_download,
        mock_upload,
        file_service,
        valid_file_upload,
        user_services,
        valid_user_data,
        db_pool,
        mock_s3_download_response,
        mock_s3_response,
):
    """Test that getting a file owned by another user raises 404 not found error."""
    mock_upload.return_value = mock_s3_response
    mock_download.return_value = mock_s3_download_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    second_user = RegisterUser(
        username="test_user2", email="test2@test.com", password="test_password2"
    )
    second_user_id = await user_services.register_new_user(
        second_user.username, second_user.email, second_user.password
    )

    await file_service.upload_an_new_file(valid_file_upload, user_id)

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM files WHERE name = $1", valid_file_upload.file_name
        )
        file_id = str(result["id"])

    with pytest.raises(HTTPException) as exc_info:
        await file_service.get_user_presigned_download_url(second_user_id, file_id)

    assert exc_info.value.status_code == 404


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_rename_file_succeeds_when_name_available(
        mock_upload,
        db_pool,
        file_service,
        user_services,
        valid_user_data,
        valid_file_upload
):
    """Test that renaming a file succeeds when new name is available."""
    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    await file_service.upload_an_new_file(valid_file_upload, user_id)

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM files WHERE name = $1",
            valid_file_upload.file_name
        )
        file_id = str(result["id"])

    await file_service.rename_file(user_id, file_id, "new_file_name_after_Test", None)

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT name FROM files WHERE id = $1",
            file_id
        )
        new_name = result["name"]

    assert new_name == "new_file_name_after_Test"


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_rename_file_fails_when_name_taken(
        mock_upload,
        db_pool,
        file_service,
        user_services,
        valid_user_data,
        valid_file_upload,
        valid_file_upload2,
        mock_s3_response
):
    """Test that renaming a file fails when target name already exists."""
    mock_upload.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    # Upload two files with different names
    await file_service.upload_an_new_file(valid_file_upload, user_id)
    await file_service.upload_an_new_file(valid_file_upload2, user_id)

    # Get the second file's ID
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM files WHERE name = $1",
            valid_file_upload2.file_name
        )
        file_id = str(result["id"])

    # Attempt to rename second file to first file's name (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await file_service.rename_file(user_id, file_id, valid_file_upload.file_name, None)

    assert exc_info.value.status_code == 409


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_rename_file_fails_when_user_not_owner(
        mock_upload,
        db_pool,
        file_service,
        user_services,
        valid_user_data,
        valid_file_upload,
        mock_s3_response
):
    """Test that renaming a file fails when user doesn't own it."""
    mock_upload.return_value = mock_s3_response

    second_user = RegisterUser(
        username="test_user_two", email="testuser2@test.com", password="test_password2"
    )

    # Register both users
    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    second_user_id = await user_services.register_new_user(
        second_user.username, second_user.email, second_user.password
    )

    # Upload file as first user
    await file_service.upload_an_new_file(valid_file_upload, user_id)

    # Get the file ID
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT id FROM files WHERE name = $1",
            valid_file_upload.file_name
        )
        file_id = str(result["id"])

    # Attempt to rename as second user (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await file_service.rename_file(second_user_id, file_id, "any_filename_test", None)

    assert exc_info.value.status_code == 404


async def test_upload_file_exceeds_storage_raises_403(
        file_service,
        user_services,
        valid_user_data,
):
    """Test that uploading a file exceeding storage quota raises 403."""
    fake_ultra_heavy_file = UploadFileInfo(
        file_name="test_video.mp4",
        file_size_in_bytes=5_400_000_000,  # 5.4GB
    )

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    with pytest.raises(HTTPException) as exc_info:
        await file_service.upload_an_new_file(fake_ultra_heavy_file, user_id)

    assert exc_info.value.status_code == 403
    assert "enough space" in exc_info.value.detail.lower()


@patch("app.services.file_services.AwsServices.generate_presigned_upload_url")
async def test_keep_both_generates_numbered_filename(
        mock_upload,
        db_pool,
        file_service,
        user_services,
        valid_user_data,
        valid_file_upload,
        mock_s3_response
):
    """Test that keep-both conflict resolution generates numbered filename."""
    mock_upload.return_value = mock_s3_response

    valid_file_replica = UploadFileInfo(
        file_name="photo.png",
        file_size_in_bytes=230,
    )

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    # Upload original file and replica with same name
    await file_service.upload_an_new_file(valid_file_upload, user_id)
    await file_service.keep_both_files(valid_file_replica, user_id)

    # Verify both files exist with correct names
    async with db_pool.acquire() as conn:
        result = await conn.fetch(
            "SELECT name FROM files WHERE owner_id = $1 ORDER BY created_at ASC",
            user_id
        )
        file_names = [dict(row) for row in result]

    assert file_names[0]["name"] == "photo.png"
    assert file_names[1]["name"] == "photo(1).png"


async def test_upload_to_nonexistent_folder_raises_400(
        file_service,
        user_services,
        valid_user_data,
):
    """Test that uploading file to nonexistent folder raises 400."""
    file_with_parent_folder = UploadFileInfo(
        file_name="photo.png",
        file_size_in_bytes=230,
        parent_folder_id="e8d52a78-7140-4d03-afd8-d0bc43cf2c9b"
    )

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    with pytest.raises(HTTPException) as exc_info:
        await file_service.upload_an_new_file(file_with_parent_folder, user_id)

    assert exc_info.value.status_code == 400