"""
Dynamic Deterioration Queue & 3× Surge Engine (v2 Hardened).
Features:
- Concurrent SQLite WAL persistence (SqliteQueueRepository) & In-Memory fallback.
- Declarative FacilityProfile safe-wait threshold adaptation.
- Multi-parametric vital velocity degradation (Delta-Vitals) and surge diversion.
"""

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from triage.facility import FacilityProfile, load_facility_profile
from triage.models import PatientRecord, Vitals

# Standard fallback safe waiting thresholds in minutes (Section 6.1)
SAFE_WAIT_THRESHOLDS: Dict[int, int] = {
    1: 0,     # Immediate bedding
    2: 10,    # Max 10 minutes
    3: 30,    # Max 30 minutes
    4: 60,    # Max 60 minutes
    5: 120,   # Max 120 minutes
}


class QueueRepository(ABC):
    """Abstract interface for queue persistence (In-Memory vs SQLite WAL vs Redis/NATS)."""

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
    """In-memory store for instantaneous test execution."""

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


class SqliteQueueRepository(QueueRepository):
    """
    Concurrent persistent SQLite queue repository with Write-Ahead Logging (WAL).
    Guarantees ACID transactions across multi-workstation readers and writers.
    """

    def __init__(self, db_path: str = "queue.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def add(self, patient: PatientRecord) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO patients (id, data_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP);",
                (patient.id, patient.model_dump_json())
            )
            conn.commit()

    def get_all(self) -> List[PatientRecord]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT data_json FROM patients ORDER BY rowid ASC;")
            rows = cursor.fetchall()
            return [PatientRecord.model_validate_json(r[0]) for r in rows]

    def update(self, patient: PatientRecord) -> None:
        self.add(patient)

    def clear(self) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM patients;")
            conn.commit()


class PatientQueue:
    """Active queue engine with deterioration scoring, vital velocity tracking, and facility profile adaptation."""

    def __init__(
        self,
        repo: Optional[QueueRepository] = None,
        facility: Optional[FacilityProfile] = None,
    ):
        self.repo = repo or SqliteQueueRepository()
        self.facility: FacilityProfile = facility or load_facility_profile("community_hospital")
        self.surge_mode: bool = False

    def set_facility(self, facility_id_or_profile: Any) -> None:
        """Dynamically updates active facility profile."""
        if isinstance(facility_id_or_profile, FacilityProfile):
            self.facility = facility_id_or_profile
        elif isinstance(facility_id_or_profile, str):
            self.facility = load_facility_profile(facility_id_or_profile)

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

        delta_hr_increase = max(0, current.heart_rate - initial.heart_rate)
        delta_sbp_drop = max(0, initial.systolic_bp - current.systolic_bp)
        delta_spo2_drop = max(0.0, initial.spo2 - current.spo2)

        penalty = (delta_hr_increase * 1.5) + (delta_sbp_drop * 2.5) + (delta_spo2_drop * 5.0)
        return round(penalty, 2)

    def calculate_priority_score(self, patient: PatientRecord) -> float:
        """
        Priority Score Invariant:
        Score = (6 - ESI) * 100 + (Wait / SafeThreshold_Facility) * 50 + ΔVitalsPenalty + PainPenalty
        """
        esi = patient.effective_esi or 3
        safe_threshold = self.facility.safe_wait_thresholds_minutes.get(esi, SAFE_WAIT_THRESHOLDS.get(esi, 30))

        base_tier_score = (6 - esi) * 100.0

        wait_ratio = (patient.wait_time_minutes / safe_threshold) if safe_threshold > 0 else 2.0
        wait_penalty = wait_ratio * 50.0

        pain_penalty = (patient.vitals.pain_scale / 10.0) * 15.0
        velocity_penalty = self.calculate_vital_velocity_penalty(patient)

        return round(base_tier_score + wait_penalty + pain_penalty + velocity_penalty, 2)

    def is_breach(self, patient: PatientRecord) -> bool:
        """Returns True if patient has exceeded the active facility's safe clinical wait time window."""
        esi = patient.effective_esi or 3
        safe_threshold = self.facility.safe_wait_thresholds_minutes.get(esi, SAFE_WAIT_THRESHOLDS.get(esi, 30))
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

        # Under 3x Surge Mode: Divert stable ESI 4 & 5 to Fast-Track (if facility supports Fast-Track)
        if not self.facility.fast_track_enabled:
            return scored_patients, []

        main_queue = []
        fast_track_queue = []

        for item in scored_patients:
            patient, score, is_breached = item
            esi = patient.effective_esi or 3
            velocity = self.calculate_vital_velocity_penalty(patient)
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