from omni_webui._compat import find_case_path, save_secret_key


def test_find_case_path(tmp_path):
    (tmp_path / ".file").touch()
    path = find_case_path(tmp_path, ".File", case_sensitive=False)
    assert path == tmp_path / ".file"
    path = find_case_path(tmp_path, ".File", case_sensitive=True)
    assert path is None


def test_save_secret_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_secret_key("123456789012")
    assert (tmp_path / ".env").read_text() == "\nOMNI_WEBUI_SECRET_KEY=123456789012\n"
