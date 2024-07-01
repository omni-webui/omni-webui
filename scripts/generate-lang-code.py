import json
from pathlib import Path

import typer

app = typer.Typer()


@app.command()
def main(
    languages_path: Path = Path(__file__).parent.parent
    / "src"
    / "lib"
    / "i18n"
    / "locales"
    / "languages.json",
):
    languages = json.loads(languages_path.read_text())
    for lang in languages:
        code = lang["code"]
        print(code.lower().replace("-", "_") + f' = "{code}"')


if __name__ == "__main__":
    app()
