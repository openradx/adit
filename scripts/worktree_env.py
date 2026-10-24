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
so a second run changes nothing. In the main checkout the script does nothing.

    uv run scripts/worktree_env.py [--slot N]
"""

import argparse
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

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


def names(worktree: str) -> dict[str, str]:
    # The CLI's compose project, and part of the session and CSRF cookie names.
    return {"STACK_NAME": f"adit_wt_{worktree}"}


PORT_STEP = 100
MAX_SLOT = 50

MARKER = re.compile(r"^# worktree slot: (\d+)\b")
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*?)\r?$")
# A local host with its port, and an http:// URL to one that leaves port 80 implicit.
LOCAL_URL_PORT = re.compile(r"(?<![\w.-])((?:[\w-]+\.)*localhost|127\.0\.0\.1):(\d+)\b")
LOCAL_URL_NO_PORT = re.compile(r"\bhttp://(?:(?:[\w-]+\.)*localhost|127\.0\.0\.1)(?![\w.:-])")


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
    if value[:1] in "\"'" and value[-1:] == value[:1]:
        return value[1:-1]
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


def clashes(base: dict[str, int], slot: int, taken: set[int]) -> set[int]:
    """Ports of `slot` that the main checkout or a taken slot also publishes.

    Two ports of PORTS a multiple of PORT_STEP apart meet in some pair of slots,
    e.g. 80 at slot 10 and 1080 at slot 0.
    """
    others = {port for other in {0, *taken} for port in shifted(base, other).values()}
    return set(shifted(base, slot).values()) & others


def choose_slot(base: dict[str, int], taken: set[int]) -> int:
    for slot in range(1, MAX_SLOT + 1):
        if slot in taken or clashes(base, slot, taken):
            continue
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

    root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd())).resolve()
    main_root, *linked = worktree_roots(root)
    if root == main_root:
        print("Main checkout (slot 0): nothing to change.")
        return

    env_file = root / ".env"
    main_env_file = main_root / ".env"
    if not env_file.is_file():
        source = main_env_file if main_env_file.is_file() else root / ENV_EXAMPLE
        shutil.copyfile(source, env_file)
        print(f"Created .env from {source}")
    # Without a main .env, the worktree's .env came from the example.
    base_file = main_env_file if main_env_file.is_file() else root / ENV_EXAMPLE
    main_env = parse_env(base_file.read_text())
    base = {var: port_value(main_env, var, default) for var, default in PORTS.items()}

    taken = {
        slot: other
        for other in linked
        if other != root and (slot := recorded_slot(other / ".env")) is not None
    }
    if args.slot is not None:
        if not 1 <= args.slot <= MAX_SLOT:
            sys.exit(f"error: --slot must be between 1 and {MAX_SLOT}")
        if args.slot in taken:
            sys.exit(f"error: slot {args.slot} is taken by {taken[args.slot]}")
        if clash := clashes(base, args.slot, set(taken)):
            sys.exit(f"error: slot {args.slot} would reuse ports {sorted(clash)}")
        slot = args.slot
    elif (own := recorded_slot(env_file)) is not None and own not in taken:
        slot = own
    else:
        slot = choose_slot(base, set(taken))

    ports = shifted(base, slot)
    worktree = re.sub(r"[^a-z0-9_-]+", "-", root.name.lower()).strip("-_") or f"slot{slot}"
    updates = {var: str(port) for var, port in ports.items()}
    updates |= names(worktree)
    updates |= moved_urls(main_env, base, ports)

    text = env_file.read_text()
    rendered = render(text, slot, updates)
    if rendered == text:
        print(f"Worktree slot {slot}: .env is up to date.")
        return
    env_file.write_text(rendered)
    print(f"Worktree slot {slot}; .env now sets:")
    for var, value in updates.items():
        print(f"  {var}={value}")


if __name__ == "__main__":
    main()
