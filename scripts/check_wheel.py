"""Check the built CLI and its bundled data outside the source checkout."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

wheel, = Path("dist").glob("*.whl")
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert "ticket_router/routing_policy.txt" in names
    assert "ticket_router/sample_data/manifest.json" in names
    assert len([name for name in names if name.startswith("ticket_router/sample_data/tickets/") and name.endswith(".json")]) == 16
    with TemporaryDirectory(prefix="ticket-routing-wheel-") as directory:
        archive.extractall(directory)
        script = '''
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from ticket_router import cli
assert Path(cli.__file__).is_relative_to(Path(sys.argv[1]))
raise SystemExit(cli.main(["--list-cases"]))
'''
        result = subprocess.run([sys.executable, "-c", script, directory], cwd=directory,
                                text=True, capture_output=True, check=True)
        data = json.loads(result.stdout)
        assert data["case_count"] == 16 and data["version"] == "1.0.0"
print("Packaged CLI, policy, manifest and 16 inputs verified outside the checkout; no model called.")
