"""
Naming utilities for AjCoach.

Persona-specific routine naming: "AjCoach - XX"
where XX = first letter + next consonant of persona name (both uppercase).

Examples:
  Alice → "AjCoach - AL"
  Bob → "AjCoach - BB"
  Carla → "AjCoach - CR"
"""


def get_persona_routine_suffix(persona_name: str) -> str:
    """
    Generate a two-letter suffix from persona name: first letter + next consonant.

    Args:
        persona_name: Name of the persona (e.g., "Alice")

    Returns:
        Two uppercase letters (e.g., "AL")

    Raises:
        ValueError: If name has fewer than 2 letters or no consonant after first letter.
    """
    if not persona_name or len(persona_name) < 2:
        raise ValueError(f"Persona name must be at least 2 characters: {persona_name}")

    first_letter = persona_name[0].upper()
    vowels = "AEIOUWY"

    # Find next consonant after first letter
    for char in persona_name[1:]:
        if char.upper() not in vowels:
            next_consonant = char.upper()
            return f"{first_letter}{next_consonant}"

    raise ValueError(f"No consonant found after first letter in: {persona_name}")


def get_persona_folder_name(persona_name: str, base_name: str = "AjCoach") -> str:
    """
    Generate folder name for persona routines.

    Args:
        persona_name: Name of the persona (e.g., "Alice")
        base_name: Prefix (default "AjCoach")

    Returns:
        Folder name (e.g., "AjCoach - AL")
    """
    suffix = get_persona_routine_suffix(persona_name)
    return f"{base_name} - {suffix}"


if __name__ == "__main__":
    # Test cases
    test_names = ["Alice", "Bob", "Carla"]
    for name in test_names:
        print(f"{name:20} → {get_persona_folder_name(name)}")
