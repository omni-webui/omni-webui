import typer
import uvicorn

from omni_webui import app

cli = typer.Typer()


@cli.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
):
    uvicorn.run(
        "omni_webui:app" if reload else app,
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
