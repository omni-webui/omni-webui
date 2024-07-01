import json


def test_settings():
    from omni_webui.config import settings

    assert settings.database_url == f"sqlite:///{settings.data_dir / "webui.db"}"


def test_config():
    from omni_webui.config import config, settings

    config_json = settings.data_dir / "config.json"
    assert not config_json.exists()
    config.webhook_url = "http://localhost:8000"
    assert config_json.exists()
    assert json.loads(config_json.read_text()) == {
        "webhook_url": "http://localhost:8000"
    }
    config.ui.default_locale = "zh-CN"
    assert config.ui.default_locale == "zh-CN"
    assert json.loads(config_json.read_text()) == {
        "webhook_url": "http://localhost:8000",
        "ui": {"default_locale": "zh-CN"},
    }
    assert config.ollama.enable
    del config.ui.default_locale
    assert json.loads(config_json.read_text()) == {
        "webhook_url": "http://localhost:8000",
        "ui": {},
    }
    del config.ui
    assert json.loads(config_json.read_text()) == {
        "webhook_url": "http://localhost:8000",
    }
