import os
import shutil
import subprocess
from pathlib import Path
from sys import stderr

from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # type: ignore


class NpmBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        def copy(src: str, dst: str):
            if not (os.path.exists(dst) and os.path.isfile(dst)):
                shutil.copy2(src, dst)

        super().initialize(version, build_data)
        print(">>> Building Omni Webui frontend\n", file=stderr)
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError(
                "`uv` is required for building Omni Webui but it was not found"
            )
        cache_dir = Path(
            subprocess.check_output([uv, "--color", "never", "cache", "dir"])
            .decode()
            .strip()
        )
        webui_dir = cache_dir.joinpath("git-v0/checkouts/d6dc8c520e52253d/29a271959")
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
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "`npm` is required for building Omni Webui but it was not found"
            )
        subprocess.run([npm, "install"], check=True)
        print("npm run build", file=stderr)
        os.environ["APP_BUILD_HASH"] = version
        subprocess.run([npm, "run", "build"], check=True)
