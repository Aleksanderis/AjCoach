#!/usr/bin/env python3
"""
Build Hevy routine JSON payload from a persona's setup_hevy.py definitions.
Usage: python -m src.hevy_routine_builder <persona_name> <routine_name>
Outputs JSON to stdout for piping to hevy_service.py update-routine.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.setup_hevy import load_persona_routines  # noqa: E402

def build_routine_payload(routines, routine_name):
    for routine in routines:
        if routine['name'] == routine_name:
            exercises = []
            superset_ids = {}
            next_superset_id = 1

            # Build exercise objects from warmups and main exercises
            warmup_list = routine.get('warmup', [])
            for superset_idx, superset in enumerate(warmup_list):
                for ex in superset:
                    sid = superset_idx + 1
                    exercises.append({
                        'exercise_template_id': ex['template_id'],
                        'superset_id': sid,
                        'notes': ex.get('notes'),
                        'sets': [
                            {
                                'type': 'warmup',
                                'weight_kg': ex.get('weight_kg'),
                                'reps': ex['reps'],
                                'duration_seconds': ex.get('duration_s'),
                                'rep_range': {'start': ex['reps'], 'end': ex['reps']}
                            }
                            for _ in range(ex['sets'])
                        ]
                    })

            # Main exercises
            for ex in routine.get('exercises', []):
                exercises.append({
                    'exercise_template_id': ex['template_id'],
                    'superset_id': None,
                    'notes': ex.get('notes'),
                    'sets': [
                        {
                            'type': 'normal',
                            'weight_kg': ex.get('weight_kg'),
                            'reps': ex.get('reps', 1),
                            'duration_seconds': ex.get('duration_s'),
                            'rep_range': {'start': ex.get('reps', 1), 'end': ex.get('reps', 1)}
                        }
                        for _ in range(ex['sets'])
                    ]
                })

            payload = {
                'routine': {
                    'title': routine['name'],
                    'notes': None,
                    'exercises': exercises
                }
            }
            return json.dumps(payload, indent=2)

    raise ValueError(f"Routine '{routine_name}' not found")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python -m src.hevy_routine_builder <persona_name> <routine_name>", file=sys.stderr)
        sys.exit(1)
    persona_routines, _ = load_persona_routines(sys.argv[1])
    print(build_routine_payload(persona_routines, sys.argv[2]))
