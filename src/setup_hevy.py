"""
Hevy routine loader — dynamically imports persona-specific setup files.

Each persona has their own setup_hevy.py in personas/<persona>/
This module loads the correct one based on the persona argument.
"""

import sys
import importlib.util
from pathlib import Path


def load_persona_routines(persona_name: str):
    """
    Dynamically load routine definitions from personas/<persona>/setup_hevy.py

    Args:
        persona_name: Name of the persona (e.g., "Alex", or your own persona folder name)

    Returns:
        (ROUTINES list, FOLDER_ID)
    """
    persona_setup_path = Path(__file__).parent.parent / "personas" / persona_name / "setup_hevy.py"

    if not persona_setup_path.exists():
        raise FileNotFoundError(f"No setup_hevy.py found for persona '{persona_name}' at {persona_setup_path}")

    spec = importlib.util.spec_from_file_location(f"setup_hevy_{persona_name}", persona_setup_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.ROUTINES, module.FOLDER_ID


# Persona folder ID registry (cache after first load).
# Populated automatically by src/persona_folders.py the first time a persona's
# Hevy folder is created — no need to fill these in by hand.
PERSONA_FOLDER_IDS = {}


def get_folder_id(persona_name: str) -> int | None:
    """Get Hevy folder ID for a persona."""
    return PERSONA_FOLDER_IDS.get(persona_name)


def register_folder_id(persona_name: str, folder_id: int):
    """Register a folder ID for a persona."""
    PERSONA_FOLDER_IDS[persona_name] = folder_id


# Default routines (for backward compatibility, load the Alex persona)
try:
    ROUTINES, FOLDER_ID = load_persona_routines("Alex")
except Exception:
    ROUTINES = []
    FOLDER_ID = None
