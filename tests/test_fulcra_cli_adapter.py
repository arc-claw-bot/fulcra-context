from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fulcra_cli_adapter.py"
spec = importlib.util.spec_from_file_location("fulcra_cli_adapter", MODULE_PATH)
fulcra_cli_adapter = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fulcra_cli_adapter)


class CommandPartsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_env = os.environ.get("FULCRA_CLI_COMMAND")

    def tearDown(self) -> None:
        if self.old_env is None:
            os.environ.pop("FULCRA_CLI_COMMAND", None)
        else:
            os.environ["FULCRA_CLI_COMMAND"] = self.old_env

    def test_preserves_explicit_multiword_command(self) -> None:
        os.environ["FULCRA_CLI_COMMAND"] = "uv tool run fulcra-api"

        self.assertEqual(fulcra_cli_adapter._command_parts(), [["uv", "tool", "run", "fulcra-api"]])

    def test_checks_executable_for_multiword_candidates(self) -> None:
        os.environ.pop("FULCRA_CLI_COMMAND", None)

        def fake_which(name: str) -> str | None:
            return "/usr/bin/uv" if name == "uv" else None

        with mock.patch.object(fulcra_cli_adapter.shutil, "which", side_effect=fake_which):
            self.assertEqual(fulcra_cli_adapter._command_parts(), [["uv", "tool", "run", "fulcra-api"]])


if __name__ == "__main__":
    unittest.main()
