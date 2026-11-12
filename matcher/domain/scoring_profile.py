"""
Scoring profile - how an employer wants candidates scored.

A profile has a name, the weight of each part of a candidate's score
(adding up to 100) and the share of the job's skills a Strong Match needs.

    ScoringProfile  one set of weights, e.g. the built-in "Balanced" profile
                    or one an employer made on the upload page
"""


def _is_whole_number(value):
    return isinstance(value, int) and not isinstance(value, bool)


class ScoringProfile:
    """How much each part of the score counts, and the Strong Match threshold.

        ScoringProfile("Skills first", {"skills": 60, "experience": 15, ...},
                       strong_match_skills=80)

    The profile checks its own values, so an invalid one can never be used
    or saved. Which parts it must weight is up to the scorer that uses it.
    """

    # The "Balanced" profile: the weights the app used before profiles existed
    DEFAULT_WEIGHTS = {
        "skills": 40,
        "experience": 25,
        "education": 10,
        "location": 10,
        "work_arrangement": 10,
        "working_hours": 5,
    }
    DEFAULT_STRONG_MATCH_SKILLS = 70

    def __init__(self, name, weights, strong_match_skills=DEFAULT_STRONG_MATCH_SKILLS, record_id=None):
        name = str(name).strip()
        if not name:
            raise ValueError("Give the scoring profile a name.")

        weights = dict(weights)
        if not weights:
            raise ValueError("A scoring profile needs at least one weight.")
        for part, weight in weights.items():
            if not _is_whole_number(weight) or not 0 <= weight <= 100:
                raise ValueError(f"The {self.label(part)} weight must be a whole number from 0 to 100.")
        total = sum(weights.values())
        if total != 100:
            raise ValueError(f"The weights must add up to 100, not {total}.")

        if not _is_whole_number(strong_match_skills) or not 0 <= strong_match_skills <= 100:
            raise ValueError("The Strong Match skills share must be a whole number from 0 to 100.")

        self._id = record_id
        self._name = name
        self._weights = weights
        self._strong_match_skills = strong_match_skills

    @classmethod
    def built_in(cls):
        """The profiles every employer can choose from, "Balanced" first."""
        return [
            cls("Balanced", cls.DEFAULT_WEIGHTS, record_id="balanced"),
            cls("Skills first", {"skills": 60, "experience": 15, "education": 5, "location": 10,
                                 "work_arrangement": 5, "working_hours": 5},
                strong_match_skills=80, record_id="skills-first"),
            cls("Experience first", {"skills": 30, "experience": 40, "education": 10, "location": 10,
                                     "work_arrangement": 5, "working_hours": 5},
                strong_match_skills=60, record_id="experience-first"),
        ]

    @classmethod
    def default(cls):
        """The "Balanced" profile, used when no profile is chosen."""
        return cls.built_in()[0]

    @staticmethod
    def label(part):
        """e.g. "work_arrangement" -> "Work arrangement"."""
        return part.replace("_", " ").capitalize()

    @property
    def id(self):
        """e.g. "balanced" for a built-in profile, "S001" for a saved one, or None."""
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def weights(self):
        """e.g. {"skills": 40, "experience": 25, ...}"""
        return dict(self._weights)

    @property
    def strong_match_skills(self):
        """The share of the job's skills (0-100%) a Strong Match needs."""
        return self._strong_match_skills

    @property
    def strong_match_ratio(self):
        """strong_match_skills as a fraction, e.g. 70 -> 0.7."""
        return self._strong_match_skills / 100

    def summary(self):
        """e.g. "Skills 40 · Experience 25 · ... · Strong Match from 70% of skills"."""
        parts = [f"{self.label(part)} {weight}" for part, weight in self._weights.items()]
        return " · ".join(parts + [f"Strong Match from {self._strong_match_skills}% of skills"])

    def to_dict(self):
        """Same shape as a record in data/scoring_profiles.json."""
        record = {} if self._id is None else {"id": self._id}
        record.update({
            "name": self._name,
            "weights": self.weights,
            "strong_match_skills": self._strong_match_skills,
        })
        return record

    @classmethod
    def from_dict(cls, record):
        """Build from a saved record. Raises ValueError if it is not a valid profile."""
        return cls(
            record.get("name", ""),
            record.get("weights", {}),
            strong_match_skills=record.get("strong_match_skills", cls.DEFAULT_STRONG_MATCH_SKILLS),
            record_id=record.get("id"),
        )
