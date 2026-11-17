"""Source-contract checks for the host/Lua console transport.

These checks make no claim about a live game process. They pin the protocol
boundaries so forensic reports can distinguish missing input from a pump or
reply failure.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ConsoleLuaPumpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = (ROOT / "src/core/fable2_console.h").read_text(encoding="utf-8")
        cls.pump = (ROOT / "src/lua/console_pump.lua").read_text(encoding="utf-8")
        cls.step = (ROOT / "src/lua/console_step.lua").read_text(encoding="utf-8")

    def test_file_transport_only_enqueues_lines_when_input_exists(self):
        poll = re.search(r"// New input file.*?// Freeze:", self.host, re.S)
        self.assertIsNotNone(poll)
        body = poll.group(0)
        self.assertIn("file_mode && (s.frames % 10) == 0", body)
        self.assertIn('s.root / "console" / "in.txt"', body)
        self.assertIn("enqueue_text(text)", body)
        self.assertLess(body.index("fs::remove(in, ec)"), body.index("enqueue_text(text)"))

    def test_lua_pump_is_started_lazily_by_a_lua_command(self):
        command = re.search(
            r"inline void run_lua_line\(.*?\n\}", self.host, re.S
        )
        self.assertIsNotNone(command)
        body = command.group(0)
        self.assertIn("if (s.pump_ready.load())", body)
        self.assertIn("dispatch_lua(line)", body)
        self.assertIn("s.lua_pending = line", body)
        self.assertRegex(body, r"if\s*\(!s\.pump_requested\)\s*start_pump\(ctx, base\)")

    def test_pending_command_is_dropped_with_an_explicit_error_if_pump_never_starts(self):
        poll = re.search(r"if \(!s\.lua_pending\.empty\(\)\).*?\n  \} else if \(s\.lua_wait\)", self.host, re.S)
        self.assertIsNotNone(poll)
        body = poll.group(0)
        self.assertIn("Clock::now() - s.pump_req_time > std::chrono::seconds(20)", body)
        self.assertIn('out("lua", "Lua commands are not ready (load a save first); dropped: " + s.lua_pending', body)
        self.assertIn("s.lua_pending.clear()", body)

    def test_dispatched_command_has_a_separate_reply_timeout(self):
        poll = re.search(r"\} else if \(s\.lua_wait\) \{.*?\n  \} else if \(s\.wait_frames", self.host, re.S)
        self.assertIsNotNone(poll)
        body = poll.group(0)
        self.assertIn("s.lua_done.load() == s.lua_seq", body)
        self.assertIn("Clock::now() >= s.lua_deadline", body)
        self.assertIn('out("lua", "no reply from the Lua command within 30 s", true)', body)

    def test_pump_protocol_uses_ready_and_sequence_matched_done_markers(self):
        self.assertIn('pcall(cprint, "[console] __f2 ready")', self.pump)
        self.assertIn('pcall(cprint, "[console] __f2 done " .. seq)', self.step)
        self.assertIn("if (body == \"__f2 ready\")", self.host)
        self.assertIn('body.rfind("__f2 done ", 0) == 0', self.host)
        self.assertIn("s.lua_done.store(std::strtoull", self.host)
        self.assertIn("s.lua_done.load() == s.lua_seq", self.host)

    def test_lua_console_output_is_appended_to_out_file(self):
        output = re.search(r"inline void out\(.*?\n\}", self.host, re.S)
        self.assertIsNotNone(output)
        self.assertIn('s.root / "console" / "out.txt"', output.group(0))
        self.assertIn("std::ios::app", output.group(0))
        self.assertIn('const std::string kTag = "[console] "', self.host)
        self.assertIn('fable2::console::out("lua", ln)', self.host)


if __name__ == "__main__":
    unittest.main()
