import plistlib
import shutil
import subprocess
import sys
import tempfile
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


def _run_with_input(cmd, text):
    proc = subprocess.run(
        cmd,
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, (
        f"Command failed: {' '.join(cmd)}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


def _iter_inline_scripts():
    for plist_path in sorted(WORKFLOWS.glob("*/info.plist")):
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        for obj in plist.get("objects", []):
            cfg = obj.get("config", {})
            script = cfg.get("script")
            if isinstance(script, str) and script.strip():
                yield plist_path, obj.get("uid", "<unknown>"), int(cfg.get("type", -1)), script


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
    zsh = shutil.which("zsh")
    for path in sh_files:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0] if path.exists() else ""
        if "zsh" in first_line:
            if zsh is None:
                print(f"Skipping zsh syntax check: {path.name} (zsh not found)")
                continue
            _run([zsh, "-n", str(path)])
        else:
            _run(["bash", "-n", str(path)])


def test_js_scripts_parse():
    node = shutil.which("node")
    if node is None:
        print("Skipping JS syntax checks: node not found")
        return
    js_files = sorted(WORKFLOWS.glob("**/*.js"))
    assert js_files, "No JS workflow scripts found"
    for path in js_files:
        _run([node, "--check", str(path)])


def test_inline_scripts_parse():
    zsh = shutil.which("zsh")
    osacompile = shutil.which("osacompile")

    for plist_path, uid, script_type, script in _iter_inline_scripts():
        label = f"{plist_path.name}:{uid}"
        if script_type == 0:  # bash
            _run_with_input(["bash", "-n"], script)
            continue
        if script_type == 5:  # zsh
            if zsh is None:
                print(f"Skipping zsh inline syntax check: {label} (zsh not found)")
                continue
            _run_with_input([zsh, "-n"], script)
            continue
        if script_type == 6:  # AppleScript
            if osacompile is None:
                print(f"Skipping AppleScript inline syntax check: {label} (osacompile not found)")
                continue
            with tempfile.TemporaryDirectory(prefix="wf-applescript-") as tmpdir:
                src = Path(tmpdir) / "inline.applescript"
                out = Path(tmpdir) / "inline.scpt"
                src.write_text(script, encoding="utf-8")
                _run([osacompile, "-o", str(out), str(src)])
            continue
        if script_type == 9:  # python
            _run_with_input(
                [sys.executable, "-c", "import sys; compile(sys.stdin.read(), '<inline>', 'exec')"],
                script,
            )
            continue


def test_no_home_bin_dependency_in_workflow_scripts():
    offenders = []
    for path in sorted(WORKFLOWS.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".sh", ".js", ".applescript", ".plist"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "~/bin/" in text or "$HOME/bin/" in text:
            offenders.append(str(path))
    assert not offenders, "Hardcoded ~/bin dependencies found:\n" + "\n".join(offenders)


def run_all():
    tests = [
        test_scriptfile_references_exist,
        test_python_scripts_compile,
        test_shell_scripts_parse,
        test_js_scripts_parse,
        test_inline_scripts_parse,
        test_no_home_bin_dependency_in_workflow_scripts,
    ]
    for fn in tests:
        fn()


if __name__ == "__main__":
    run_all()
