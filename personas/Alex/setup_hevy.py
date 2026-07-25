"""
Alex's Hevy routine definitions.

Single source of truth for routine structure: exercises, warm-ups, sets, reps,
starting weights, and exercise notes. This is a template — copy this file into
your own persona folder and replace with your real routines.

FOLDER_ID is the Hevy routine folder ID for this persona. Leave it as None until
you've created the folder in Hevy (via /sync-hevy) — it gets filled in automatically.
"""

FOLDER_ID = None

ROUTINES = [
    {
        "name": "Upper Push/Pull (Mon)",
        "routine_id": None,  # filled in automatically after first sync to Hevy
        "folder_id": FOLDER_ID,
        "warmup": [
            [
                {"name": "Stretching", "template_id": "527DA061", "sets": 1, "duration_s": 360,
                 "notes": "Pre-workout — dynamic mobility before warmup supersets."},
            ],
            [
                {"name": "Wall Angels", "template_id": "92fa5ee5-33ae-4915-b050-508de1a328e6", "sets": 2, "reps": 10,
                 "notes": "Back flat on wall, goalpost arms. Slide overhead keeping wall contact."},
                {"name": "Band Pullaparts", "template_id": "E8D86EE8", "sets": 2, "reps": 15,
                 "notes": "Arms straight at chest height, pull band apart to chest."},
            ],
        ],
        "exercises": [
            {"name": "Bench Press (Dumbbell)", "template_id": "3601968B", "sets": 3, "reps": 10, "weight_kg": 20.0,
             "notes": "Starting weight — adjust after first session based on RPE."},
            {"name": "Seated Cable Row - V Grip (Cable)", "template_id": "0393F233", "sets": 3, "reps": 10, "weight_kg": 30.0,
             "notes": "Starting weight — adjust after first session."},
            {"name": "Bird Dog", "template_id": "BD0AD077", "sets": 3, "reps": 10,
             "notes": "10 reps per side. Opposite arm and leg extend, 2-sec hold."},
            {"name": "Treadmill", "template_id": "243710DE", "sets": 1, "duration_s": 1500,
             "notes": "Zone 2 — target 111-140 bpm"},
            {"name": "Stretching & Mobility Cool-Down", "template_id": "527DA061", "sets": 1, "duration_s": 360,
             "notes": "Post-workout mobility — see profile.md cool-down protocol."},
        ],
    },
]
