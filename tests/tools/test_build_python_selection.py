import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt" and Path("D:/QA-Storage").is_dir(),
                     "build.cmd storage guard requires Windows D:\\QA-Storage")
class BuildPythonSelectionTests(unittest.TestCase):
    def test_configure_does_not_override_cmake_python_discovery(self):
        root = Path(__file__).resolve().parents[2]
        fixture_root = Path("D:/QA-Storage/guard-tests/build-python-selection")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temp:
            work = Path(temp)
            shutil.copy(root / "build.cmd", work / "build.cmd")
            for folder in ("tools", "generated/default", "thirdparty/rexglue-sdk", "bin",
                           "preferred-cmake"):
                (work / folder).mkdir(parents=True, exist_ok=True)
            shutil.copy(root / "tools/qa_storage_guard.py", work / "tools/qa_storage_guard.py")
            for name in ("generated/rexglue.cmake", "generated/default/sources.cmake",
                         "thirdparty/rexglue-sdk/CMakeLists.txt"):
                (work / name).touch()
            (work / "tools/build_runtime_sdk.cmd").write_text("@exit /b 0\n")
            (work / "bin/cmake.cmd").write_text(
                '@echo %*>>"%CMAKE_ARGS%"\n@echo %TEMP%>>"%TEMP_ARGS%"\n@exit /b 0\n')
            (work / "preferred-cmake/cmake.cmd").write_text(
                '@echo preferred>>"%CMAKE_SOURCE%"\n@echo %*>>"%CMAKE_ARGS%"\n'
                '@echo %TEMP%>>"%TEMP_ARGS%"\n@exit /b 0\n')
            (work / "bin/clang++.cmd").write_text("@exit /b 0\n")
            (work / "bin/ninja.cmd").write_text("@exit /b 0\n")
            env = os.environ.copy()
            env["PATH"] = str(work / "bin") + os.pathsep + env["PATH"]
            env["CMAKE_ARGS"] = str(work / "args.txt")
            env["TEMP_ARGS"] = str(work / "temp-args.txt")
            env["CMAKE_SOURCE"] = str(work / "cmake-source.txt")
            env["FABLE2_CMAKE_BIN"] = str(work / "preferred-cmake")
            env.pop("FABLE2_STORAGE_GUARD_ACTIVE", None)
            result = subprocess.run(["cmd", "/c", str(work / "build.cmd"), "-release", "fable_2"],
                                    env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Python3_EXECUTABLE", (work / "args.txt").read_text())
            self.assertEqual((work / "cmake-source.txt").read_text().strip(), "preferred")
            redirected_temp = (work / "temp-args.txt").read_text().strip()
            self.assertTrue(redirected_temp.startswith(str(Path("D:/QA-Storage/fable2-active/runs"))),
                            redirected_temp)


if __name__ == "__main__":
    unittest.main()
