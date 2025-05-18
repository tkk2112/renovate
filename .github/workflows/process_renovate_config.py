#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

def run_validator(config_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['npx', '--yes', '--package', 'renovate',
         '--', 'renovate-config-validator', str(config_path)],
        capture_output=True,
        text=True,
        check=False
    )

def extract_new_config(stdout: str) -> dict:
    marker = '"newConfig":'
    idx = stdout.find(marker)
    if idx < 0:
        return {}
    # find the opening brace
    start = stdout.find('{', idx)
    if start < 0:
        raise ValueError("Could not locate '{' after newConfig")
    # walk forward to match braces
    depth = 0
    for pos, ch in enumerate(stdout[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                block = stdout[start:pos+1]
                return json.loads(block)
    raise ValueError("Unbalanced braces in newConfig")

def diff_top_level(old: dict, new: dict) -> list[str]:
    diffs = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) != new.get(key):
            diffs.append(f"{key!r}: {old.get(key)!r} → {new.get(key)!r}")
    return diffs

def main():
    parser = argparse.ArgumentParser(
        description="Run renovate-config-validator and migrate default.json if needed"
    )
    parser.add_argument('config', type=Path, help="Path to default.json")
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"ERROR: {args.config} not found", file=sys.stderr)
        sys.exit(1)

    result = run_validator(args.config)
    # uncomment to debug:
    # print(result.stdout, result.stderr)

    if "Config migration necessary" not in result.stdout:
        print("✅ No migration needed.")
        sys.exit(0)

    current = json.loads(args.config.read_text())
    try:
        new = extract_new_config(result.stdout)
    except Exception as e:
        print(f"ERROR parsing newConfig: {e}", file=sys.stderr)
        sys.exit(1)

    diffs = diff_top_level(current, new)
    if not diffs:
        print("⚠️  Validator said migration needed but configs are identical.")
        sys.exit(0)

    print("🛠️  Applying migration:")
    for line in diffs:
        print("  •", line)

    # overwrite default.json
    args.config.write_text(json.dumps(new, indent=2) + "\n")
    # touch a marker file for the workflow to pick up
    Path('changes_made.txt').write_text('true')
    sys.exit(0)

if __name__ == "__main__":
    main()
