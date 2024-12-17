from omni_webui.models.user import get_password_hash, verify_password


def test_password():
    password = "P@$$W0RD"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
