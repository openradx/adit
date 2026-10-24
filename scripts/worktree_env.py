#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Give a git worktree of this repository its own host ports and Compose projects.

Claude Code copies the main checkout's .env into each worktree it creates
(.worktreeinclude), so without this a worktree's stacks would publish the same
host ports as the main checkout's and, where a project name is fixed, take over
its containers and volumes.

Each linked worktree gets a slot N >= 1; the main checkout is slot 0. Every port
in PORTS becomes the main checkout's value + N * PORT_STEP, a URL in .env that
points at one of those ports moves with it, and the names from names() become
unique to the worktree. The slot is recorded at the top of the worktree's .env,
with the worktree's path, so a copy of that .env elsewhere is not taken for the
slot's owner. Later runs keep what the worktree's .env sets apart from the main
checkout's values, ports and names alike, and only fill in the rest; a worktree
set up by hand before keeps its own the same way. --slot rewrites them all. In
the main checkout the script changes nothing.

Every checkout, the main one included, also records its ports in a directory
shared by the projects on this machine that use this script (REGISTRY). A
worktree takes no slot whose ports another checkout, of this repository or any
other, has recorded, whether or not that stack is running. A port of this
checkout that another checkout also records is only warned about, with a free
one to set in .env instead.

    uv run --script scripts/worktree_env.py [--slot N]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

ENV_EXAMPLE = "example.env"

# Every host port the development stack publishes, with the default
# docker-compose.dev.yml applies when .env leaves it unset.
PORTS = {
    "WEB_DEV_PORT": 8000,
    "POSTGRES_DEV_PORT": 5432,
    "REMOTE_DEBUGGING_PORT": 5678,
    "RECEIVER_DEV_PORT": 11122,
    "ORTHANC1_DEV_PORT": 7501,
    "ORTHANC2_DEV_PORT": 7502,
}


def names(worktree: str, slot: int) -> dict[str, str]:
    # The CLI's compose project, and part of the session and CSRF cookie names.
    return {"STACK_NAME": f"adit_wt{slot}_{worktree}"}


PORT_STEP = 100
MAX_SLOT = 50
REGISTRY = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "dev-ports"

MARKER = re.compile(r"^# worktree slot: (\d+) of (.+) \(ports ")
MARKER_LINE = re.compile(r"^# worktree slot: ")
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*?)\r?$")
# A local host with its port, and an http:// URL to one that leaves port 80 implicit.
LOCAL_URL_PORT = re.compile(r"(?<![\w.-])((?:[\w-]+\.)*localhost|127\.0\.0\.1):(\d+)\b")
LOCAL_URL_NO_PORT = re.compile(r"\bhttp://(?:(?:[\w-]+\.)*localhost|127\.0\.0\.1)(?![\w.:-])")
# The password of a URL, hidden in the printed summary.
URL_PASSWORD = re.compile(r"(://[^:/?#@\s]*:)[^/?#@\s]+@")


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def worktree_roots(cwd: Path) -> list[Path]:
    """All worktrees of the repository, the main checkout first.

    Empty for a bare repository, which has no main checkout to take ports from.
    """
    entries = git("worktree", "list", "--porcelain", cwd=cwd).split("\n\n")
    if "bare" in entries[0].splitlines():
        return []
    return [Path(entry.splitlines()[0].removeprefix("worktree ")).resolve() for entry in entries]


def parse_env(text: str) -> dict[str, str]:
    """Raw values by name; like dotenv, a later assignment wins."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        if match := ASSIGNMENT.match(line):
            env[match[1]] = match[2].strip()
    return env


def unquote(value: str) -> str:
    """The value as dotenv reads it: inside its quotes, or before an inline comment."""
    if value and value[0] in "\"'" and (end := value.find(value[0], 1)) != -1:
        return value[1:end]
    return value.split(" #", 1)[0].strip()


def port_value(env: dict[str, str], var: str, default: int) -> int:
    try:
        return int(unquote(env.get(var, "")))
    except ValueError:
        return default


def marker(env_file: Path) -> tuple[int, Path] | None:
    """The slot recorded in `env_file`, and the checkout it was recorded for."""
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        if MARKER_LINE.match(line):
            match = MARKER.match(line)
            return (int(match[1]), Path(match[2])) if match else (0, Path())
    return None


def own_slot(checkout: Path) -> int | None:
    """The slot `checkout` holds; None for a .env copied from another checkout."""
    found = marker(checkout / ".env")
    return found[0] if found and found[1] == checkout else None


def in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def shifted(base: dict[str, int], slot: int) -> dict[str, int]:
    return {var: port + slot * PORT_STEP for var, port in base.items()}


@contextmanager
def registry_lock() -> Iterator[None]:
    """Hold the registry while this run reads the records and writes its own.

    Two checkouts set up at once, as parallel agents do, would otherwise both
    see the same slot as free.
    """
    lock: TextIO | None
    try:
        REGISTRY.mkdir(parents=True, exist_ok=True)
        lock = (REGISTRY / ".lock").open("w")
    except OSError:
        lock = None  # record() reports the unwritable registry
    if lock is None:
        yield
        return
    with lock:
        if sys.platform != "win32":
            import fcntl

            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
            except OSError as error:  # e.g. ENOLCK on a network home
                print(f"warning: could not lock {REGISTRY}: {error}")
        yield


def replace_file(path: Path, text: str) -> None:
    """Write `text` to `path` through a temporary file, so no reader sees half of it."""
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as tmp:
        tmp.write(text)
    if path.exists():
        shutil.copymode(path, tmp.name)
    os.replace(tmp.name, path)


def claims(root: Path) -> list[tuple[str, str, int]]:
    """(checkout, variable, port) for the ports every other checkout records."""
    found = []
    for file in sorted(REGISTRY.glob("*.json")):
        try:
            entry = json.loads(file.read_text())
        except (OSError, ValueError):
            continue  # pruned by a concurrent run, or not JSON
        if not Path(entry["checkout"]).is_dir():
            try:
                file.unlink(missing_ok=True)  # the checkout was deleted
            except OSError:
                pass  # a read-only registry keeps the record; it is ignored above
        elif entry["checkout"] != str(root):
            found += [(entry["checkout"], var, port) for var, port in entry["ports"].items()]
    return found


def record(root: Path, ports: dict[str, int]) -> None:
    entry = {"checkout": str(root), "ports": ports}
    target = REGISTRY / f"{hashlib.sha256(str(root).encode()).hexdigest()[:16]}.json"
    try:
        REGISTRY.mkdir(parents=True, exist_ok=True)
        replace_file(target, json.dumps(entry, indent=2))
    except OSError as error:
        print(f"warning: could not record the ports in {REGISTRY}: {error}")


def local_ports(value: str) -> set[int]:
    found = {int(match[2]) for match in LOCAL_URL_PORT.finditer(value)}
    return found | ({80} if LOCAL_URL_NO_PORT.search(value) else set())


def warn_about_claims(
    ports: dict[str, int], claimed: list[tuple[str, str, int]], env: dict[str, str]
) -> bool:
    """Warn about each port another checkout records; `env` is what .env sets."""
    used = set(ports.values()) | {port for _, _, port in claimed}
    warned = False
    for var, port in ports.items():
        if owners := [f"{checkout} ({other})" for checkout, other, p in claimed if p == port]:
            free = next(p for p in range(port + 1, 65536) if p not in used and not in_use(p))
            used.add(free)
            warned = True
            urls = [name for name, value in env.items() if port in local_ports(value)]
            print(
                f"warning: {var}={port} is also used by {', '.join(owners)};"
                f" set another port in .env, e.g. {var}={free}"
                + (f", and move {', '.join(urls)} to it" if urls else "")
            )
    return warned


def clashes(base: dict[str, int], slot: int, taken: set[int]) -> set[int]:
    """Ports of `slot` that the main checkout or a taken slot also publishes.

    Two ports of PORTS a multiple of PORT_STEP apart meet in some pair of slots,
    e.g. 80 at slot 10 and 1080 at slot 0.
    """
    others = {port for other in {0, *taken} for port in shifted(base, other).values()}
    return set(shifted(base, slot).values()) & others


def open_slots(base: dict[str, int], taken: set[int], claimed: set[int]) -> list[int]:
    """Slots none of whose ports another checkout, of any repository, uses."""
    return [
        slot
        for slot in range(1, MAX_SLOT + 1)
        if slot not in taken
        and not clashes(base, slot, taken)
        and not set(shifted(base, slot).values()) & claimed
    ]


def choose_slot(base: dict[str, int], taken: set[int], claimed: set[int]) -> int:
    for slot in open_slots(base, taken, claimed):
        busy = [port for port in shifted(base, slot).values() if in_use(port)]
        if not busy:
            return slot
        print(f"slot {slot}: ports {busy} are in use, trying the next one")
    sys.exit(f"error: no free slot below {MAX_SLOT + 1}")


def moved_urls(
    main_env: dict[str, str], base: dict[str, int], ports: dict[str, int]
) -> dict[str, str]:
    """Main-checkout values that point at a local port which moves, rewritten."""
    moves = {str(base[var]): str(ports[var]) for var in base}

    def move(match: re.Match[str]) -> str:
        return f"{match[1]}:{moves.get(match[2], match[2])}"

    def add_port(match: re.Match[str]) -> str:
        return f"{match[0]}:{moves['80']}" if "80" in moves else match[0]

    updates = {}
    for var, value in main_env.items():
        if var in base:
            continue
        moved = LOCAL_URL_NO_PORT.sub(add_port, LOCAL_URL_PORT.sub(move, value))
        if moved != value:
            updates[var] = moved
    return updates


def render(text: str, slot: int, root: Path, updates: dict[str, str]) -> str:
    """Apply `updates` to .env text in place, keeping its comments and order.

    The last assignment of a variable is replaced; a variable that is only
    present commented out is uncommented; any other is appended.
    """
    lines = [line for line in text.splitlines(keepends=True) if not MARKER_LINE.match(line)]
    appended = []
    for var, value in updates.items():
        assigned = [
            i for i, line in enumerate(lines) if (m := ASSIGNMENT.match(line)) and m[1] == var
        ]
        commented = re.compile(rf"^\s*#\s*{var}\s*=")
        if assigned:
            index = assigned[-1]
        elif found := [i for i, line in enumerate(lines) if commented.match(line)]:
            index = found[0]
        else:
            appended.append(f"{var}={value}\n")
            continue
        lines[index] = f"{var}={value}\n"
    if appended:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines += ["\n# Worktree (scripts/worktree_env.py)\n", *appended]
    header = (
        f"# worktree slot: {slot} of {root} (ports are the main checkout's"
        f" + {slot * PORT_STEP}; written by scripts/worktree_env.py)\n"
    )
    return header + "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Give this git worktree its own host ports and names in .env."
    )
    parser.add_argument("--slot", type=int, help="use this slot instead of the next free one")
    args = parser.parse_args()
    with registry_lock():
        configure(args.slot)


def configure(requested: int | None) -> None:
    try:
        root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd())).resolve()
    except (OSError, subprocess.CalledProcessError) as error:
        # A copy without git, or a checkout git refuses to read (another owner, a
        # .git file pointing at another machine's path): the command must still run.
        detail = getattr(error, "stderr", None) or error
        print(f"Not a git checkout git can read ({str(detail).strip()}).")
        print("Worktree ports are not managed here.")
        return
    git_dir = Path(git("rev-parse", "--absolute-git-dir", cwd=root)).resolve()
    common_dir = (root / git("rev-parse", "--git-common-dir", cwd=root)).resolve()
    is_main = git_dir == common_dir  # also with a separate git dir or a submodule
    roots = worktree_roots(root)
    if not roots:
        print("Bare repository: worktree ports are not managed.")
        return
    main_root, *linked = [root, *roots[1:]] if is_main else roots
    env_file = root / ".env"
    main_env_file = main_root / ".env"
    # Without a main .env, a worktree's .env comes from the example.
    base_file = main_env_file if main_env_file.is_file() else root / ENV_EXAMPLE
    main_env = parse_env(base_file.read_text())
    base = {var: port_value(main_env, var, default) for var, default in PORTS.items()}
    claimed = claims(root)
    claimed_ports = {port for _, _, port in claimed}
    if is_main:
        record(root, base)
        warn_about_claims(base, claimed, main_env)
        return

    if not env_file.is_file():
        shutil.copy2(base_file, env_file)
        print(f"Created .env from {base_file}")

    current = parse_env(env_file.read_text())
    copied = marker(env_file) is not None and own_slot(root) is None
    # What this worktree sets apart from the main checkout is its own.
    kept = {var: value for var, value in current.items() if value != main_env.get(var)}
    taken = {
        slot: other for other in linked if other != root and (slot := own_slot(other)) is not None
    }
    if requested is not None:
        if not 1 <= requested <= MAX_SLOT:
            sys.exit(f"error: --slot must be between 1 and {MAX_SLOT}")
        if requested in taken:
            sys.exit(f"error: slot {requested} is taken by {taken[requested]}")
        if clash := clashes(base, requested, set(taken)):
            sys.exit(f"error: slot {requested} would reuse ports {sorted(clash)}")
        if recorded := sorted(set(shifted(base, requested).values()) & claimed_ports):
            sys.exit(f"error: slot {requested} would reuse ports {recorded} of another checkout")
        slot = requested
        kept = {}
    elif (own := own_slot(root)) is not None and own not in taken:
        slot = own
    else:
        if marker(env_file):
            kept = {}  # a copy of another worktree's .env, or a slot held twice
        slot = choose_slot(base, set(taken), claimed_ports)

    ports = {var: port_value(kept, var, port) for var, port in shifted(base, slot).items()}
    # Short enough for a DNS label (<service>.<project>.internal) with any suffix.
    worktree = re.sub(r"[^a-z0-9_-]+", "-", root.name.lower())[:32].strip("-_")
    updates = {var: str(port) for var, port in ports.items()}
    # The slot keeps the names apart where worktree directory names coincide.
    named = names(worktree or "worktree", slot)
    updates |= {var: kept.get(var, value) for var, value in named.items()}
    updates |= moved_urls(main_env, base, ports)
    record(root, ports)
    # The names in a copy are another worktree's, so nothing of this one's is left.
    if not copied and (
        renamed := [
            f"{var}={current[var]}"
            for var in named
            if current.get(var) not in (None, updates[var], main_env.get(var))
        ]
    ):
        print(
            f"note: {', '.join(renamed)} change; what still runs under the old names"
            " keeps its containers, ports and volumes until you stop it"
        )
    if warn_about_claims(ports, claimed, current | updates) and (
        free := open_slots(base, set(taken), claimed_ports)
    ):
        action = "reset" if free[0] == slot else "move"
        print(f"  or {action} this worktree's ports to free ones: --slot {free[0]}")

    text = env_file.read_text()
    rendered = render(text, slot, root, updates)
    if rendered == text:
        print(f"Worktree slot {slot}: .env is up to date.")
        return
    replace_file(env_file, rendered)
    print(f"Worktree slot {slot}; .env now sets:")
    for var, value in updates.items():
        print(f"  {var}={URL_PASSWORD.sub(r'\1***@', value)}")


if __name__ == "__main__":
    main()
