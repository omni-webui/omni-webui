from typer.testing import CliRunner

from omni_webui.main import cli

runner = CliRunner()


def test_cli():
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("Omni WebUI v")
