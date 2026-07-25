import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class HRZone:
    min: int
    max: int

class PersonaService:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.hr_zones: Dict[int, HRZone] = {}
        self.medical_context: str = ""
        self._parse()

    def _parse(self):
        if not os.path.exists(self.file_path):
            return

        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract HR Zones from the Markdown table
        # Pattern: | **Zone X** | ... | Min - Max bpm |
        zone_matches = re.findall(r"Zone (\d+).*?(\d+)\s*-\s*(\d+)\s*bpm", content)
        for z_num, z_min, z_max in zone_matches:
            self.hr_zones[int(z_num)] = HRZone(min=int(z_min), max=int(z_max))

        # Extract Medical Context (Cough/Airway issues)
        if "Clinical Investigations" in content:
            medical_section = content.split("## 4. Current Medical Context")[1].split("## 5.")[0]
            self.medical_context = medical_section.strip()

    def get_zone(self, hr: int) -> int:
        for zone_num, bounds in self.hr_zones.items():
            if bounds.min <= hr <= bounds.max:
                return zone_num
        if hr > self.hr_zones.get(5, HRZone(0, 198)).max:
            return 5
        return 0
