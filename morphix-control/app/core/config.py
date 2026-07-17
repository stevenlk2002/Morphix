import os


def _project_root():
    # app/core/config.py -> morphix-control/
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings:
    def __init__(self):
        root = _project_root()
        self.DB_PATH = os.environ.get(
            "MORPHIX_DB", os.path.join(root, "data", "morphix.db")
        )
        self.DATA_DIR = os.path.join(root, "data")
        self.DEVICE_PROVISIONING_KEY = os.environ.get(
            "DEVICE_PROVISIONING_KEY", "dev-provisioning-key"
        )
        self.DEV_MODE = os.environ.get("MORPHIX_DEV", "1") == "1"
        self.HEARTBEAT_INTERVAL_SEC = int(os.environ.get("HEARTBEAT_INTERVAL_SEC", "30"))
        self.COMMAND_POLL_INTERVAL_SEC = int(
            os.environ.get("COMMAND_POLL_INTERVAL_SEC", "5")
        )
        self.TOKEN_TTL_SEC = int(os.environ.get("TOKEN_TTL_SEC", str(60 * 60 * 24 * 30)))


_settings = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
