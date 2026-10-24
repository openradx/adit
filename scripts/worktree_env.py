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
unique to the worktree. The slot is recorded at the top of the worktree's .env;
later runs keep the ports already set there and only fill in missing ones, so a
port changed by hand or moved off a busy port stays, until --slot rewrites them
all. In the main checkout the script changes nothing.

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

MARKER = re.compile(r"^# worktree slot: (\d+)\b")
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
    """All worktrees of the repository, the main checkout first."""
    porcelain = git("worktree", "list", "--porcelain", cwd=cwd)
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in porcelain.splitlines()
        if line.startswith("worktree ")
    ]


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


def recorded_slot(env_file: Path) -> int | None:
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        if match := MARKER.match(line):
            return int(match[1])
    return None


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

            fcntl.flock(lock, fcntl.LOCK_EX)
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
            file.unlink(missing_ok=True)  # the checkout was deleted
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


def warn_about_claims(ports: dict[str, int], claimed: list[tuple[str, str, int]]) -> bool:
    used = set(ports.values()) | {port for _, _, port in claimed}
    warned = False
    for var, port in ports.items():
        if owners := [f"{checkout} ({other})" for checkout, other, p in claimed if p == port]:
            free = next(p for p in range(port + 1, 65536) if p not in used and not in_use(p))
            used.add(free)
            warned = True
            print(
                f"warning: {var}={port} is also used by {', '.join(owners)};"
                f" set another port in .env, e.g. {var}={free}"
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


def render(text: str, slot: int, updates: dict[str, str]) -> str:
    """Apply `updates` to .env text in place, keeping its comments and order.

    The last assignment of a variable is replaced; a variable that is only
    present commented out is uncommented; any other is appended.
    """
    lines = [line for line in text.splitlines(keepends=True) if not MARKER.match(line)]
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
        f"# worktree slot: {slot} (ports are the main checkout's + {slot * PORT_STEP};"
        " written by scripts/worktree_env.py)\n"
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
    root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd())).resolve()
    main_root, *linked = worktree_roots(root)
    env_file = root / ".env"
    main_env_file = main_root / ".env"
    # Without a main .env, a worktree's .env comes from the example.
    base_file = main_env_file if main_env_file.is_file() else root / ENV_EXAMPLE
    main_env = parse_env(base_file.read_text())
    base = {var: port_value(main_env, var, default) for var, default in PORTS.items()}
    claimed = claims(root)
    claimed_ports = {port for _, _, port in claimed}
    if root == main_root:
        record(root, base)
        warn_about_claims(base, claimed)
        return

    if not env_file.is_file():
        shutil.copyfile(base_file, env_file)
        print(f"Created .env from {base_file}")

    kept: dict[str, str] = {}
    taken = {
        slot: other
        for other in linked
        if other != root and (slot := recorded_slot(other / ".env")) is not None
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
    elif (own := recorded_slot(env_file)) is not None and own not in taken:
        slot = own
        kept = parse_env(env_file.read_text())
    else:
        slot = choose_slot(base, set(taken), claimed_ports)

    ports = {var: port_value(kept, var, port) for var, port in shifted(base, slot).items()}
    worktree = re.sub(r"[^a-z0-9_-]+", "-", root.name.lower()).strip("-_") or "worktree"
    updates = {var: str(port) for var, port in ports.items()}
    # The slot keeps the names apart where worktree directory names coincide.
    updates |= names(worktree, slot)
    updates |= moved_urls(main_env, base, ports)
    record(root, ports)
    if warn_about_claims(ports, claimed) and (free := open_slots(base, set(taken), claimed_ports)):
        action = "reset" if free[0] == slot else "move"
        print(f"  or {action} this worktree's ports to free ones: --slot {free[0]}")

    text = env_file.read_text()
    rendered = render(text, slot, updates)
    if rendered == text:
        print(f"Worktree slot {slot}: .env is up to date.")
        return
    replace_file(env_file, rendered)
    print(f"Worktree slot {slot}; .env now sets:")
    for var, value in updates.items():
        print(f"  {var}={URL_PASSWORD.sub(r'\1***@', value)}")


if __name__ == "__main__":
    main()
