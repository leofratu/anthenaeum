from __future__ import annotations

from pathlib import Path

import pytest
import typer

from athenaeum.cli.config_util import config_network_value
from athenaeum.cli.io_util import as_report_text, make_run_id, write_new_text_file, write_text_file


def test_config_network_value_maps_states() -> None:
    assert config_network_value("disabled") == "disabled"
    assert config_network_value("enabled") == "enabled"
    assert config_network_value("auto") == "enabled"


def test_as_report_text_prefers_markdown_field() -> None:
    assert as_report_text({"report_markdown": "# Hi"}).startswith("# Hi")
    assert as_report_text("plain") == "plain"


def test_make_run_id_is_stable_with_seed() -> None:
    assert make_run_id("q", 7) == make_run_id("q", 7)
    assert make_run_id("q", 7) != make_run_id("q", 8)


def test_write_new_text_file_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    write_text_file(path, "a\n", overwrite=True)
    with pytest.raises(typer.BadParameter, match="already exists"):
        write_new_text_file(path, "b\n")
