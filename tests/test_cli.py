from pathlib import Path

import pytest
from typer.testing import CliRunner

from omni_webui.main import cli

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("Omni WebUI v")


def test_migrate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path
    dotenv = tmp_path / ".env"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dummy_file = tmp_path / ".webui_secret_key"
    dummy_file.write_text("123456789012")

    result = runner.invoke(cli, ["migrate", str(data_dir)])
    assert result.stdout.startswith("Uploads directory not found")

    (data_dir / "uploads").mkdir()
    assert not (tmp_path / "dest").exists()
    result = runner.invoke(
        cli,
        [
            "migrate",
            str(data_dir),
            "--dest-dir",
            str(tmp_path / "dest"),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "dest").exists()
    assert "OMNI_WEBUI_SECRET_KEY=123456789012" in dotenv.read_text()
