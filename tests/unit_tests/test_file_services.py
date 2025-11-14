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