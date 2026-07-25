#!/usr/bin/env python3
"""
Hevy folder operations for personas.

Functions for creating and registering persona folders in Hevy.
Called by /sync-hevy skill when a persona needs a folder created.
"""

import subprocess
import json
import sys
from pathlib import Path
from src.naming import get_persona_folder_name


def get_existing_folder(persona: str, folder_name: str) -> dict | None:
    """Find if folder already exists in Hevy."""
    result = subprocess.run(
        ["python", "src/hevy_service.py", "--persona", persona, "get-routine-folders"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    folders = json.loads(result.stdout).get("data", [])
    for folder in folders:
        if folder.get("name") == folder_name:
            return folder
    return None


def create_folder_in_hevy(persona: str) -> int:
    """
    Create a new folder for persona in Hevy.
    Returns the folder ID.
    Raises RuntimeError if creation fails.
    """
    folder_name = get_persona_folder_name(persona)

    # Check if folder already exists
    existing = get_existing_folder(persona, folder_name)
    if existing:
        return existing["id"]

    # Create new folder
    body = json.dumps({"name": folder_name})
    result = subprocess.run(
        ["python", "src/hevy_service.py", "--persona", persona, "create-routine-folder", "--data", body],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create folder {folder_name}: {result.stderr}")

    response = json.loads(result.stdout)
    folder_id = response.get("data", {}).get("id")
    if not folder_id:
        raise RuntimeError(f"No folder ID in response: {response}")

    return folder_id


def register_folder_id(persona: str, folder_id: int):
    """
    Store folder ID in setup_hevy.py PERSONA_FOLDER_IDS.
    Called after folder is created in Hevy.
    """
    setup_path = Path("src/setup_hevy.py")
    content = setup_path.read_text()

    # Don't update if already registered
    if f'"{persona}"' in content:
        return

    new_entry = f'    "{persona}": {folder_id},  # {get_persona_folder_name(persona)}\n'

    # Insert before closing }
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == '}' and 'PERSONA_FOLDER_IDS' in '\n'.join(lines[max(0, i-10):i]):
            lines.insert(i, new_entry)
            break

    setup_path.write_text('\n'.join(lines))
