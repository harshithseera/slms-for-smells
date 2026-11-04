"""Small statistics helpers for attendance numbers."""
from __future__ import annotations


def mean_session_minutes(sessions: list[float]) -> float:
    total = 0.0
    count = 0
    for s in sessions:
        total += s
        count += 1
    return total / count if count else 0.0


def geometric_mean_session_minutes(sessions: list[float]) -> float:
    product = 1.0
    count = 0
    for s in sessions:
        product *= s
        count += 1
    return product ** (1 / count) if count else 0.0


def session_summary(sessions: list[float], as_text: bool = False) -> dict | str:
    stats = {"count": len(sessions), "mean": mean_session_minutes(sessions), "longest": max(sessions, default=0.0)}
    if as_text:
        return f"{stats['count']} sessions, mean {stats['mean']:.1f} min, longest {stats['longest']:.0f} min"
    return stats


def occupancy(booked: int, capacity: int) -> float:
    return round(booked / capacity, 2) if capacity else 0.0
