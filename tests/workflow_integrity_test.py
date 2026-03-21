import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"


def _run(cmd):
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, (
        f"Command failed: {' '.join(cmd)}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


def test_scriptfile_references_exist():
    for plist_path in sorted(WORKFLOWS.glob("*/info.plist")):
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        workflow_dir = plist_path.parent
        for obj in plist.get("objects", []):
            cfg = obj.get("config", {})
            scriptfile = cfg.get("scriptfile")
            if isinstance(scriptfile, str) and scriptfile:
                target = workflow_dir / scriptfile
                assert target.is_file(), f"Missing scriptfile target: {target}"


def test_python_scripts_compile():
    py_files = sorted(WORKFLOWS.glob("**/*.py"))
    assert py_files, "No python workflow scripts found"
    for path in py_files:
        _run([sys.executable, "-m", "py_compile", str(path)])


def test_shell_scripts_parse():
    sh_files = sorted(WORKFLOWS.glob("**/*.sh")) + [ROOT / "build.sh", ROOT / "dev-setup.sh"]
    assert sh_files, "No shell scripts found"
    for path in sh_files:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0] if path.exists() else ""
        if "zsh" in first_line:
            _run(["zsh", "-n", str(path)])
        else:
            _run(["bash", "-n", str(path)])


def test_js_scripts_parse():
    node = shutil.which("node")
    assert node is not None, "node is required to syntax-check JS workflow scripts"
    js_files = sorted(WORKFLOWS.glob("**/*.js"))
    assert js_files, "No JS workflow scripts found"
    for path in js_files:
        _run([node, "--check", str(path)])


def run_all():
    tests = [
        test_scriptfile_references_exist,
        test_python_scripts_compile,
        test_shell_scripts_parse,
        test_js_scripts_parse,
    ]
    for fn in tests:
        fn()


if __name__ == "__main__":
    run_all()
