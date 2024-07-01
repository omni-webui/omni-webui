import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_env(tmp_path_factory):
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
