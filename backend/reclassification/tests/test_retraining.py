from __future__ import annotations

import pytest

from backend.reclassification.managers.reclassification_manager import ReclassificationError, ReclassificationManager
from backend.reclassification.managers.retraining_manager import RetrainingManager


def test_retraining_does_not_start_twice() -> None:
    manager = ReclassificationManager()
    retraining = RetrainingManager(manager)
    trigger = retraining.trigger_retraining("manual", "super_admin")
    manager._retraining_running = True
    with pytest.raises(ReclassificationError):
        retraining.trigger_retraining("manual", "super_admin")
    manager._retraining_running = False
    assert retraining.run_retraining(trigger.trigger_id) is True
    assert manager.triggers[trigger.trigger_id].status == "completed"
