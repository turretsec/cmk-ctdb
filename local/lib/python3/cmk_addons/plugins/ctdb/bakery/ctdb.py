from pathlib import Path
from typing import Generator

from cmk.base.plugins.bakery.bakery_api.v1 import (
    OS,
    Plugin,
    PluginConfig,
    register,
)


def _get_ctdb_files(conf: dict) -> Generator:
    yield Plugin(
        base_os=OS.LINUX,
        source=Path("ctdb_status.py"),
        target=Path("ctdb_status.py"),
    )

    if conf:
        yield PluginConfig(
            base_os=OS.LINUX,
            lines=_build_cfg_lines(conf),
            target=Path("ctdb_status.cfg"),
        )


def _build_cfg_lines(conf: dict) -> list:
    lines = ["[ctdb_status]"]

    if timeout := conf.get("timeout"):
        lines.append(f"timeout = {timeout}")

    return lines


register.bakery_plugin(
    name="ctdb",
    files_function=_get_ctdb_files,
)