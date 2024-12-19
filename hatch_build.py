import os
import shutil
import subprocess
from pathlib import Path
from sys import stderr

from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # type: ignore


def _(name: str):
    e = shutil.which(name)
    if e is None:
        raise RuntimeError(
            f"`{name}` is required for building Omni Webui but it was not found"
        )
    return e


uv = _("uv")
git = _("git")
deno = _("deno")
_("npm")


def is_ignored(path: str) -> bool:
    rules = [
        rule[2:]
        for rule in (Path(__file__).parent / ".gitignore").read_text().splitlines()
        if rule.strip() and rule.startswith("!/src")
    ]
    rpath = Path(path).relative_to(Path.cwd())
    return rpath not in rules


def copy(src: str, dst: str):
    if is_ignored(dst):
        shutil.copy2(src, dst)


class DenoBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)
        print(">>> Building Omni Webui frontend\n", file=stderr)  # noqa: T201

        cache_dir = Path(
            subprocess.check_output([uv, "--color", "never", "cache", "dir"])
            .decode()
            .strip()
        )
        webui_dir = cache_dir.joinpath("git-v0/checkouts/d6dc8c520e52253d/29a271959")
        if not webui_dir.exists():
            # TODO: currently solution is so dirty, need to find a better way to clone the repo
            subprocess.run(
                [
                    git,
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    "v0.4.8",
                    "https://github.com/open-webui/open-webui",
                    webui_dir,
                ],
                check=True,
            )
        build_dir = Path.cwd()
        directories = [
            "src",
            "static",
        ]
        for dir in directories:
            shutil.copytree(
                webui_dir / dir, build_dir / dir, dirs_exist_ok=True, copy_function=copy
            )
        files = [
            "i18next-parser.config.ts",
            "postcss.config.js",
            "svelte.config.js",
            "tailwind.config.js",
            "tsconfig.json",
        ]
        for f in files:
            shutil.copy2(webui_dir / f, build_dir / f)
        if deno is None:
            raise RuntimeError(
                "`deno` is required for building Omni Webui but it was not found"
            )
        subprocess.run([deno, "install"], check=True)
        print("deno task build", file=stderr)  # noqa: T201
        os.environ["APP_BUILD_HASH"] = version
        subprocess.run([deno, "task", "build"], check=True)
