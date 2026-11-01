"""Select the legacy Solutions API or the current CPU Tasks implementation."""
import mediapipe as mp

if hasattr(mp, 'solutions'):
    from .legacy import generate_annotation
else:
    from .tasks import generate_annotation
