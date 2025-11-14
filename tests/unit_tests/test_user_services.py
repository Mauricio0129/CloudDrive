from fastapi.exceptions import HTTPException
import pytest


async def test_registering_duplicate_username_raises_409(
    user_services, valid_user_data
):
    await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    with pytest.raises(HTTPException) as exc_info:
        await user_services.register_new_user(
            valid_user_data.username, "other@test.com", valid_user_data.password
        )

    assert exc_info.value.status_code == 409


async def test_registering_duplicate_email_raises_409(user_services, valid_user_data):
    await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )

    with pytest.raises(HTTPException) as exc_info:
        await user_services.register_new_user(
            "otheruser", valid_user_data.email, valid_user_data.password
        )

    assert exc_info.value.status_code == 409


async def test_querying_unregistered_username_data_raises_404(user_services):
    with pytest.raises(HTTPException) as exc_info:
        await user_services.get_user_id_and_password("nonexistentuser")

    assert exc_info.value.status_code == 404


async def test_querying_unregistered_email_data_raises_404(user_services):
    with pytest.raises(HTTPException) as exc_info:
        await user_services.get_user_id_and_password("nonexistent@email.com")

    assert exc_info.value.status_code == 404


async def test_querying_registered_user_username_user_data(
    user_services, valid_user_data
):
    await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )
    data = await user_services.get_user_id_and_password(valid_user_data.username)

    assert data["id"] is not None
    assert data["password"] is not None
    assert len(data["id"]) == 36
    assert len(data["password"]) == 60


async def test_querying_registered_user_email_user_data(user_services, valid_user_data):
    await user_services.register_new_user(
        valid_user_data.username, valid_user_data.email, valid_user_data.password
    )
    data = await user_services.get_user_id_and_password(valid_user_data.email)
    assert data["id"] is not None
    assert data["password"] is not None
    assert len(data["id"]) == 36
    assert len(data["password"]) == 60
