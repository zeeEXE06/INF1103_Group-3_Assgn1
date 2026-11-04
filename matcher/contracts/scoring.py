"""
Scoring contract - one part of a candidate's match score.

A candidate's score is the sum of its components' points, e.g. skills
(weight 40) + experience (weight 25) + ... = up to 100. Each subclass
only decides what fraction of its weight a candidate earns, so a new part
of the score is a new subclass, with no change to the scorer.
"""

from abc import ABC, abstractmethod


class ScoreComponent(ABC):
    """Abstract base for one weighted part of a candidate's score."""

    def __init__(self, weight):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise ValueError(f"A score weight must be a number of 0 or more, not {weight!r}")
        self._weight = weight

    @property
    def weight(self):
        """The most points this component can give."""
        return self._weight

    @property
    @abstractmethod
    def name(self):
        """Short name, e.g. "skills"."""

    @abstractmethod
    def fraction(self, candidate):
        """How much of this part the candidate meets, from 0.0 to 1.0."""

    def points(self, candidate):
        """The points this candidate earns: weight x fraction (kept between 0 and weight)."""
        return self._weight * min(1.0, max(0.0, self.fraction(candidate)))
