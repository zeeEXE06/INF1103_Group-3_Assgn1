"""
JobStatus - where a background AI job is up to (used by the threaded
processing in P5).

    PENDING -> RUNNING -> DONE
                       -> FAILED
"""

from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

    @property
    def is_finished(self):
        """True once the job has a result or an error, so the page can stop waiting."""
        return self in (JobStatus.DONE, JobStatus.FAILED)

    def can_move_to(self, next_status):
        """True if a job in this status may move to next_status."""
        return next_status in _NEXT_STATUSES[self]


_NEXT_STATUSES = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.DONE, JobStatus.FAILED},
    JobStatus.DONE: set(),
    JobStatus.FAILED: set(),
}
