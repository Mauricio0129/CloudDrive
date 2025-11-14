from app.services.file_services import FileServices
from fastapi import HTTPException
from app.schemas.schemas import UploadFileInfo
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
    """Mock S3 presigned URL response."""
    return {
        "url": "https://mock-bucket.s3.amazonaws.com/",
        "fields": {
            "key": "files/user-id/file-id",
            "AWSAccessKeyId": "MOCK_KEY",
            "policy": "mock_policy",
            "signature": "mock_signature"
        }
    }


@patch('app.services.file_services.AwsServices.generate_presigned_upload_url')
async def test_uploading_new_file_succeeds(mock_aws, file_service, valid_file_upload,
                                           user_services, valid_user_data, mock_s3_response):
    """Test that uploading a new file with unique name returns S3 presigned URL."""

    mock_aws.return_value = mock_s3_response  # Tell mock what to return

    # Now create user
    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    # When this runs, it calls the mocked AWS method and gets mock_s3_response back
    response = await file_service.upload_an_new_file(valid_file_upload, user_id)

    # Verify it worked
    assert response["url"] is not None
    mock_aws.assert_called_once()  # Verify the mock was called

@patch('app.services.file_services.AwsServices.generate_presigned_upload_url')
async def test_uploading_duplicate_file_raises_409(mock_aws, file_service, valid_file_upload,
                                           user_services, valid_user_data, mock_s3_response):
    """Test that uploading a file with existing name raises 409 without conflict resolution."""

    mock_aws.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    # First upload succeeds
    await file_service.upload_an_new_file(valid_file_upload, user_id)

    # Second upload with same name should fail
    with pytest.raises(HTTPException) as exc_info:
        await file_service.upload_an_new_file(valid_file_upload, user_id)

    assert exc_info.value.status_code == 409

@patch('app.services.file_services.AwsServices.generate_presigned_upload_url')
async def test_replacing_existing_file_succeeds(mock_aws, file_service, valid_file_upload, larger_file_upload,
                                                user_services, valid_user_data, mock_s3_response):
    """Test that replacing an existing file with 'Replace' conflict strategy returns presigned URL."""

    mock_aws.return_value = mock_s3_response

    user_id = await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    # Upload original file
    await file_service.upload_an_new_file(valid_file_upload, user_id)

    # Replace with larger file
    response = await file_service.replace_existing_file(larger_file_upload, user_id)
    print(response)
    assert response["url"] is not None