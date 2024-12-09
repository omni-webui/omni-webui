import os
from pathlib import Path

import typer
import uvicorn

from omni_webui import app
from omni_webui.config import get_env, get_settings
from omni_webui.logging import logger

cli = typer.Typer()


settings = get_settings()
env = get_env()

os.environ["FROM_INIT_PY"] = "true"

if os.getenv("WEBUI_SECRET_KEY") is None:
    os.environ["WEBUI_SECRET_KEY"] = settings.secret_key

if os.getenv("USE_CUDA_DOCKER", "false") == "true":
    logger.info(
        "CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries."
    )
    env.LD_LIBRARY_PATH.extend(
        [
            Path("/usr/local/lib/python3.11/site-packages/torch/lib"),
            Path("/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"),
        ]
    )
    os.environ["LD_LIBRARY_PATH"] = env.model_dump()["LD_LIBRARY_PATH"]

from open_webui.main import app as open_webui_app  # noqa: E402

app.mount("/", open_webui_app)


@cli.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
):
    uvicorn.run(
        "omni_webui.__main__:app" if reload else app,
        host=host,
        port=port,
        reload=reload,
        forwarded_allow_ips="*",
    )


@cli.command()
def version():
    from importlib.metadata import PackageNotFoundError, version

    try:
        v = "v" + version("omni_webui")
    except PackageNotFoundError:
        v = "(unknown version)"
    typer.echo(f"Omni WebUI {v}")


if __name__ == "__main__":
    cli()
