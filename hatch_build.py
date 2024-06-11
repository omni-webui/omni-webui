# noqa: INP001
import os
import shutil
import subprocess
from sys import stderr

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)
        stderr.write(">>> Building Omni Webui frontend\n")
        bun = shutil.which("bun")
        if bun is None:
            raise RuntimeError(
                "NodeJS `npm` is required for building Omni Webui but it was not found"
            )
        stderr.write("### bun install\n")
        subprocess.run([bun, "install"], check=True)  # noqa: S603
        stderr.write("\n### npm run build\n")
        os.environ["APP_BUILD_HASH"] = version
        subprocess.run([bun, "run", "build"], check=True)  # noqa: S603
