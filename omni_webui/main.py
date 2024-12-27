import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import fsspec
import typer
import uvicorn

from omni_webui import __version__
from omni_webui._compat import save_secret_key
from omni_webui.config import D

if TYPE_CHECKING:
    from s3fs import S3FileSystem

cli = typer.Typer()


@cli.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
):
    uvicorn.run(
        "omni_webui.app:app",
        host=host,
        port=port,
        reload=reload,
        forwarded_allow_ips="*",
    )


@cli.command()
def version():
    typer.echo(f"Omni WebUI v{__version__}")


@cli.command()
def migrate(
    data_dir: Annotated[Path, typer.Argument(exists=True)],
    dest_dir: Path = D.user_data_path,
    secret_key: str = "",
    dotenv: Path | None = None,
    s3_bucket: str = "",
):
    """Migrate from Open WebUI to Omni WebUI."""

    if secret_key == "" and (key_path := Path.cwd() / ".webui_secret_key").exists():
        secret_key = key_path.read_text().strip()
    if secret_key:
        save_secret_key(secret_key, dotenv)

    upload_dir = data_dir / "uploads"
    if not upload_dir.exists():
        typer.echo(f"Uploads directory not found: {upload_dir}")
        raise typer.Abort()

    shutil.copytree(data_dir, dest_dir, dirs_exist_ok=True)

    if s3_bucket:
        fs: S3FileSystem = fsspec.filesystem("s3")
        fs.put(upload_dir, f"{s3_bucket}/uploads", recursive=True)
        typer.echo(f"Uploads uploaded to: {s3_bucket}/uploads")

    typer.echo(f"Data migrated to: {dest_dir}")
