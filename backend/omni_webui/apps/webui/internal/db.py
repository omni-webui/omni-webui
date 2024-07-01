import json

from loguru import logger
from omni_webui.config import OMNI_WEBUI_DIR, settings
from peewee import TextField
from peewee_migrate import Router


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)


if (ollama_db := settings.data_dir / "ollama.db").exists():
    ollama_db.rename(settings.data_dir / "webui.db")
    logger.info("Database migrated from Ollama-WebUI successfully.")


logger.info(f"Connected to a {settings.database.__class__.__name__} database.")
router = Router(
    settings.database,
    migrate_dir=OMNI_WEBUI_DIR / "apps" / "webui" / "internal" / "migrations",
    logger=logger,
)
router.run()
