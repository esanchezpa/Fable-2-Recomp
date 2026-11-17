from pathlib import Path

# unittest discover -s tests imports this package as ``tools``. Include the
# repository's command modules so tests can import tools.<module> consistently.
__path__.append(str(Path(__file__).resolve().parents[2] / "tools"))
