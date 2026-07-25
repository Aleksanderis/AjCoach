#!/usr/bin/env python3
"""Stop hook: auto-commit & push working changes, but ONLY when the session is in
an auto-accept / bypass permission mode. No-op in normal/plan mode.

Derives a meaningful Conventional Commit message from what actually changed.
Cross-platform: invoked via exec form, works under bash, Git Bash, PowerShell.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter

AUTO_MODES = {"acceptEdits", "bypassPermissions", "auto"}

# (regex, type, scope-template, description)
# Patterns are tested in order; first match wins per file.
# {0} = first capture group (usually persona name or skill name).
FILE_PATTERNS = [
    (r"^personas/([^/]+)/reports/",       "chore",  "reports/{0}",  "update coaching reports"),
    (r"^personas/([^/]+)/stats/",          "chore",  "data/{0}",     "sync garmin stats"),
    (r"^personas/([^/]+)/program/",        "docs",   "program/{0}",  "update training plan"),
    (r"^personas/([^/]+)/profile\.md$",    "docs",   "profile/{0}",  "update athlete profile"),
    (r"^\.claude/skills/([^/]+)/",         "feat",   "skills/{0}",   "update {0} skill"),
    (r"^\.claude/hooks/",                  "chore",  "hooks",        "update hooks"),
    (r"^\.claude/settings",                "chore",  "config",       "update settings"),
    (r"^src/",                             "feat",   "src",          "update source"),
    (r"^docker/",                          "chore",  "docker",       "update docker config"),
    (r"^personas/([^/]+)/",               "chore",  "{0}",          "update persona files"),
    (r"^(CLAUDE\.md|README\.md)$",         "docs",   "docs",         "update documentation"),
    (r"^\.gitattributes$",                 "chore",  "git",          "update git config"),
]


def categorise(files):
    """Return list of (type, scope, description) for each file."""
    results = []
    for f in files:
        for pattern, typ, scope_tpl, desc_tpl in FILE_PATTERNS:
            m = re.match(pattern, f)
            if m:
                g = m.group(1) if m.lastindex else ""
                scope = scope_tpl.format(g)
                desc  = desc_tpl.format(g)
                results.append((typ, scope, desc))
                break
        else:
            results.append(("chore", "misc", "update working changes"))
    return results


def build_message(files):
    if not files:
        return "chore: auto-commit working changes"

    cats = categorise(files)

    # Dominant commit type (feat > docs > chore in tie-break priority)
    type_priority = {"feat": 0, "fix": 1, "docs": 2, "chore": 3}
    type_counts = Counter(c[0] for c in cats)
    dominant_type = min(type_counts, key=lambda t: type_priority.get(t, 9))

    # Among files of the dominant type, find the dominant scope
    dominant_cats = [c for c in cats if c[0] == dominant_type]
    scope_counts = Counter(c[1] for c in dominant_cats)
    dominant_scope, scope_freq = scope_counts.most_common(1)[0]

    # Description: most common description among files in the dominant scope
    desc_counts = Counter(
        c[2] for c in dominant_cats if c[1] == dominant_scope
    )
    dominant_desc = desc_counts.most_common(1)[0][0]

    # If files span multiple distinct scopes, try to widen to a shared parent.
    if len(scope_counts) > 1:
        # e.g. "reports/Example" and "program/Example" → "Example"
        # e.g. "config" and "hooks" → both are single-part → no shared parent → drop scope
        second_parts = [s.split("/")[1] for s in scope_counts if "/" in s]
        top_parts    = [s.split("/")[0] for s in scope_counts]
        if second_parts and len(set(second_parts)) == 1:
            # All multi-part scopes share the same second component (persona name)
            dominant_scope = second_parts[0]
            desc_counts2 = Counter(
                c[2] for c in dominant_cats
                if c[1].endswith("/" + dominant_scope) or c[1] == dominant_scope
            )
            dominant_desc = (desc_counts2 or desc_counts).most_common(1)[0][0]
        elif len(set(top_parts)) == 1:
            # All scopes share the same top-level prefix (e.g. all "src/…")
            dominant_scope = top_parts[0]
        else:
            # Truly mixed (e.g. config + hooks): drop scope
            dominant_scope = None
            dominant_desc = desc_counts.most_common(1)[0][0]

    if dominant_scope:
        return f"{dominant_type}({dominant_scope}): {dominant_desc}"
    return f"{dominant_type}: {dominant_desc}"


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if (data.get("permission_mode") or "") not in AUTO_MODES:
        return 0

    cwd = data.get("cwd") or os.getcwd()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    def git(*args, timeout=20):
        try:
            return subprocess.run(
                ["git", *args], cwd=cwd, env=env,
                capture_output=True, text=True, timeout=timeout,
            )
        except Exception:
            return None

    inside = git("rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0:
        return 0

    status = git("status", "--porcelain")
    if status is None or status.returncode != 0 or not status.stdout.strip():
        return 0

    staged = git("add", "-A")
    if staged is None or staged.returncode != 0:
        return 0

    # Derive message from what's now staged
    diff = git("diff", "--cached", "--name-only")
    files = [f.strip() for f in (diff.stdout or "").splitlines() if f.strip()]
    msg = build_message(files)

    committed = git("commit", "-q", "-m", msg)
    if committed is None or committed.returncode != 0:
        return 0

    # Before pushing, try a fast-forward pull to sync with any remote changes.
    # If the remote has diverging commits, we can't push safely — wake the user.
    pull = git("pull", "--ff-only", "-q")

    if pull and pull.returncode == 0:
        # Pull succeeded; now push
        git("push", "-q")
        print(json.dumps({"systemMessage": f"Auto-committed and pushed: \"{msg}\""}))
        return 0
    else:
        # Pull failed: remote has diverging commits. Commits are safe locally,
        # but can't push until conflicts are resolved. Wake the user.
        msg_short = msg[:50] + "..." if len(msg) > 50 else msg
        print(json.dumps({
            "systemMessage": f"Auto-committed but can't push: \"{msg_short}\". Remote has diverging commits. Run: git pull --rebase"
        }))
        return 2  # exit code 2 triggers asyncRewake to notify the user


if __name__ == "__main__":
    sys.exit(main())
