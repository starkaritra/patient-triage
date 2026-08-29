"""
Dynamic Deterioration Queue & 3× Surge Engine.
Manages safe-wait time windows, real-time priority scores, and fast-track diversion.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from triage.models import PatientRecord


# Maximum safe waiting thresholds in minutes (Section 5.1)
SAFE_WAIT_THRESHOLDS: Dict[int, int] = {
    1: 0,     # Immediate bedding
    2: 10,    # Max 10 minutes
    3: 30,    # Max 30 minutes
    4: 60,    # Max 60 minutes
    5: 120,   # Max 120 minutes
}


class QueueRepository(ABC):
    """Abstract interface for queue persistence (In-Memory vs Redis/SQL)."""

    @abstractmethod
    def add(self, patient: PatientRecord) -> None:
        pass

    @abstractmethod
    def get_all(self) -> List[PatientRecord]:
        pass

    @abstractmethod
    def update(self, patient: PatientRecord) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class InMemoryQueueRepository(QueueRepository):
    """In-memory store for instantaneous execution."""

    def __init__(self):
        self._store: Dict[str, PatientRecord] = {}

    def add(self, patient: PatientRecord) -> None:
        self._store[patient.id] = patient

    def get_all(self) -> List[PatientRecord]:
        return list(self._store.values())

    def update(self, patient: PatientRecord) -> None:
        self._store[patient.id] = patient

    def clear(self) -> None:
        self._store.clear()


class PatientQueue:
    """Active queue engine with deterioration scoring and surge adaptation."""

    def __init__(self, repo: Optional[QueueRepository] = None):
        self.repo = repo or InMemoryQueueRepository()
        self.surge_mode: bool = False

    @staticmethod
    def calculate_priority_score(patient: PatientRecord) -> float:
        """
        Priority Score Formula:
        Score = (6 - ESI) * 100 + (Wait / SafeThreshold) * 50 + DeltaVitals
        """
        esi = patient.effective_esi or 3
        safe_threshold = SAFE_WAIT_THRESHOLDS.get(esi, 30)

        base_tier_score = (6 - esi) * 100.0

        wait_ratio = (patient.wait_time_minutes / safe_threshold) if safe_threshold > 0 else 2.0
        wait_penalty = wait_ratio * 50.0

        pain_penalty = (patient.vitals.pain_scale / 10.0) * 15.0

        return round(base_tier_score + wait_penalty + pain_penalty, 2)

    @staticmethod
    def is_breach(patient: PatientRecord) -> bool:
        """Returns True if patient has exceeded safe clinical wait time window."""
        esi = patient.effective_esi or 3
        safe_threshold = SAFE_WAIT_THRESHOLDS.get(esi, 30)
        return patient.wait_time_minutes > safe_threshold

    def get_ranked_queues(self) -> Tuple[List[Tuple[PatientRecord, float, bool]], List[Tuple[PatientRecord, float, bool]]]:
        """
        Returns: (main_emergency_queue, fast_track_queue)
        Each item is: (patient, priority_score, is_breached)
        """
        all_patients = self.repo.get_all()
        scored_patients = [
            (p, self.calculate_priority_score(p), self.is_breach(p))
            for p in all_patients
        ]

        # Sort descending by priority score
        scored_patients.sort(key=lambda item: item[1], reverse=True)

        if not self.surge_mode:
            return scored_patients, []

        # Under 3x Surge Mode: Divert stable ESI 4 & 5 to Fast-Track
        main_queue = []
        fast_track_queue = []

        for item in scored_patients:
            patient, score, is_breached = item
            esi = patient.effective_esi or 3
            if esi in (4, 5) and not is_breached:
                fast_track_queue.append(item)
            else:
                main_queue.append(item)

        return main_queue, fast_track_queue

    def simulate_time_advance(self, minutes: int = 15) -> None:
        """Advances wait time for all waiting patients."""
        for p in self.repo.get_all():
            p.wait_time_minutes += minutes
            self.repo.update(p)

    def simulate_vital_decompensation(self, patient_id: str) -> Optional[PatientRecord]:
        """Simulates acute vital deterioration for a waiting patient."""
        for p in self.repo.get_all():
            if p.id == patient_id:
                p.vitals.systolic_bp = max(60, p.vitals.systolic_bp - 25)
                p.vitals.heart_rate = min(170, p.vitals.heart_rate + 30)
                p.vitals.spo2 = max(86.0, p.vitals.spo2 - 6.0)
                self.repo.update(p)
                return p
        return None