"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
_delegate = initialize_adapter(globals(), "motion.pose")
