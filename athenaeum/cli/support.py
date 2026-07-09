"""CLI support facade.

Prefer importing from focused modules:
- ``io_util`` — files, JSON, run ids
- ``config_util`` — config load/write
- ``sessions_util`` — sessions, daemon wakes, resume
- ``run`` — question execution
- ``runtime_util`` — runtime selection / spawn orchestration
- ``errors`` — fail-loud contracts

This module re-exports the public surface so existing ``from athenaeum.cli.support import …``
imports keep working.
"""

from __future__ import annotations

from athenaeum.cli.config_util import (
    active_provider_base_url,
    config_defaults,
    config_network_value,
    primary_config_text,
    prompt_bool,
    reasoning_for_interactive_config,
    write_interactive_config,
)
from athenaeum.cli.io_util import (
    as_report_text,
    emit_json,
    make_run_id,
    mode_artifacts,
    write_new_text_file,
    write_output,
    write_text_file,
)
from athenaeum.cli.run import (
    handle_question,
    handle_question_from_state,
    print_interactive_message,
    report_schema,
)
from athenaeum.cli.runtime_util import (
    run_selected_runtime,
    select_requested_runtime,
)
from athenaeum.cli.sessions_util import (
    consume_due_wakes,
    continue_run,
    print_resume_state,
    set_session_status,
)

__all__ = [
    "active_provider_base_url",
    "as_report_text",
    "config_defaults",
    "config_network_value",
    "consume_due_wakes",
    "continue_run",
    "emit_json",
    "handle_question",
    "handle_question_from_state",
    "make_run_id",
    "mode_artifacts",
    "primary_config_text",
    "print_interactive_message",
    "print_resume_state",
    "prompt_bool",
    "reasoning_for_interactive_config",
    "report_schema",
    "run_selected_runtime",
    "select_requested_runtime",
    "set_session_status",
    "write_interactive_config",
    "write_new_text_file",
    "write_output",
    "write_text_file",
]
