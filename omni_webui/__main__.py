import typer
import uvicorn

from omni_webui import __version__

app = typer.Typer()


@app.command()
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


@app.command()
def version():
    typer.echo(f"Omni WebUI v{__version__}")


app()
