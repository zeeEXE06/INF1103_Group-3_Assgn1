"""
Contracts - the abstract base classes the managers are built on.

    ai.py       AIProvider (talks to an AI model) and AITask (one kind of request)
    data.py     RecordRepository (saves and loads records)
    scoring.py  ScoreComponent (one part of a candidate's score)

Callers depend on these classes, not on a concrete implementation, so the
real Gemini provider or JSON files can be swapped for test doubles.
"""
