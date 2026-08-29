"""
Dynamic Deterioration Queue & 3× Surge Engine (v1 Hardened).
Manages safe-wait time windows, multi-parametric vital velocity degradation (Delta-Vitals),
breach alerts, and fast-track diversion.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from triage.models import PatientRecord, Vitals


# Maximum safe waiting thresholds in minutes (Section 6.1)
SAFE_WAIT_THRESHOLDS: Dict[int, int] = {
    1: 0,     # Immediate bedding
    2: 10,    # Max 10 minutes
    3: 30,    # Max 30 minutes
    4: 60,    # Max 60 minutes
    5: 120,   # Max 120 minutes
}


class QueueRepository(ABC):
    """Abstract interface for queue persistence (In-Memory vs Redis/NATS/SQL)."""

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
    """Active queue engine with deterioration scoring, vital velocity tracking, and surge adaptation."""

    def __init__(self, repo: Optional[QueueRepository] = None):
        self.repo = repo or InMemoryQueueRepository()
        self.surge_mode: bool = False

    @staticmethod
    def calculate_vital_velocity_penalty(patient: PatientRecord) -> float:
        """
        Computes vital deterioration velocity penalty when serial vitals are re-recorded.
        Penalty = 1.5 * ΔHR + 2.5 * (-ΔSBP) + 5.0 * (-ΔSpO2)
        """
        if not patient.vitals_history:
            return 0.0

        initial = patient.vitals_history[0]
        current = patient.vitals

        # Positive values represent clinical deterioration
        delta_hr_increase = max(0, current.heart_rate - initial.heart_rate)
        delta_sbp_drop = max(0, initial.systolic_bp - current.systolic_bp)
        delta_spo2_drop = max(0.0, initial.spo2 - current.spo2)

        penalty = (delta_hr_increase * 1.5) + (delta_sbp_drop * 2.5) + (delta_spo2_drop * 5.0)
        return round(penalty, 2)

    @classmethod
    def calculate_priority_score(cls, patient: PatientRecord) -> float:
        """
        Priority Score Invariant:
        Score = (6 - ESI) * 100 + (Wait / SafeThreshold) * 50 + ΔVitalsPenalty + PainPenalty
        """
        esi = patient.effective_esi or 3
        safe_threshold = SAFE_WAIT_THRESHOLDS.get(esi, 30)

        base_tier_score = (6 - esi) * 100.0

        wait_ratio = (patient.wait_time_minutes / safe_threshold) if safe_threshold > 0 else 2.0
        wait_penalty = wait_ratio * 50.0

        pain_penalty = (patient.vitals.pain_scale / 10.0) * 15.0
        velocity_penalty = cls.calculate_vital_velocity_penalty(patient)

        return round(base_tier_score + wait_penalty + pain_penalty + velocity_penalty, 2)

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
            velocity = self.calculate_vital_velocity_penalty(patient)
            # Only divert if stable, non-breached, and no rapid vital decompensation
            if esi in (4, 5) and not is_breached and velocity == 0.0:
                fast_track_queue.append(item)
            else:
                main_queue.append(item)

        return main_queue, fast_track_queue

    def simulate_time_advance(self, minutes: int = 15) -> None:
        """Advances wait time for all waiting patients."""
        for p in self.repo.get_all():
            p.wait_time_minutes += minutes
            self.repo.update(p)

    def record_vital_update(self, patient_id: str, new_vitals: Vitals) -> Optional[PatientRecord]:
        """Appends existing vitals to history and applies new vital measurements."""
        for p in self.repo.get_all():
            if p.id == patient_id:
                p.vitals_history.append(p.vitals.model_copy(deep=True))
                p.vitals = new_vitals
                self.repo.update(p)
                return p
        return None

    def simulate_vital_decompensation(self, patient_id: str) -> Optional[PatientRecord]:
        """Simulates acute vital decompensation with history tracking."""
        for p in self.repo.get_all():
            if p.id == patient_id:
                # Snapshot initial vitals if not already recorded
                if not p.vitals_history:
                    p.vitals_history.append(p.vitals.model_copy(deep=True))
                
                updated_vitals = p.vitals.model_copy(deep=True)
                updated_vitals.systolic_bp = max(60, updated_vitals.systolic_bp - 25)
                updated_vitals.heart_rate = min(175, updated_vitals.heart_rate + 35)
                updated_vitals.spo2 = max(86.0, updated_vitals.spo2 - 6.0)
                updated_vitals.recorded_at = datetime.utcnow()
                
                p.vitals = updated_vitals
                self.repo.update(p)
                return p
        return None