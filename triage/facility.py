"""
Declarative Facility Profile Loader & Registry (v2 Pillar 4).
Loads YAML/JSON facility configurations to dynamically adjust
safe-wait thresholds, imaging capabilities, and transfer protocols.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResourceCapabilities(BaseModel):
    has_ct_scanner: bool = True
    has_mri: bool = False
    has_cath_lab: bool = False
    has_pediatric_icu: bool = False
    has_trauma_resus_bay: bool = True


class FacilityProfile(BaseModel):
    """Declarative facility configuration contract."""
    facility_id: str = Field(..., description="Unique facility slug, e.g. level1_trauma")
    facility_name: str = Field(..., description="Human-readable hospital name")
    tier: str = Field("Community Emergency Department", description="Hospital classification tier")
    safe_wait_thresholds_minutes: Dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 10, 3: 30, 4: 60, 5: 120},
        description="Maximum safe waiting windows in minutes per ESI tier"
    )
    resource_capabilities: ResourceCapabilities = Field(default_factory=ResourceCapabilities)
    surge_trigger_occupancy_pct: float = Field(80.0, ge=50.0, le=100.0)
    fast_track_enabled: bool = True
    auto_transfer_protocols: Dict[str, bool] = Field(default_factory=dict)


def _parse_simple_yaml(content: str) -> Dict[str, Any]:
    """Zero-dependency YAML parser for nested clinical facility configuration files."""
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        pass

    # Clean fallback parser for flat and 1-level nested YAML
    data: Dict[str, Any] = {}
    current_dict: Optional[Dict[str, Any]] = None
    current_key: Optional[str] = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if ":" not in stripped:
            continue

        k, v = stripped.split(":", 1)
        k = k.strip()
        v = v.strip()

        # Remove surrounding quotes
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]

        # Convert scalar types
        val: Any = v
        if v.lower() == "true":
            val = True
        elif v.lower() == "false":
            val = False
        elif v.isdigit():
            val = int(v)
        else:
            try:
                val = float(v)
            except ValueError:
                val = v

        if indent == 0:
            if not v:  # Sub-dictionary header
                current_dict = {}
                current_key = k
                data[k] = current_dict
            else:
                current_dict = None
                current_key = None
                data[k] = val
        elif indent > 0 and current_dict is not None:
            # Sub-key
            sub_k: Any = int(k) if k.isdigit() else k
            current_dict[sub_k] = val

    return data


FACILITY_CACHE: Dict[str, FacilityProfile] = {}


def get_facilities_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "config" / "facilities"


def list_available_facilities() -> List[str]:
    """Returns list of all available facility IDs in config/facilities/."""
    fdir = get_facilities_dir()
    if not fdir.exists():
        return ["community_hospital"]
    files = [f.stem for f in fdir.glob("*.yaml")] + [f.stem for f in fdir.glob("*.yml")]
    return sorted(list(set(files))) if files else ["community_hospital"]


def load_facility_profile(facility_id: str = "community_hospital") -> FacilityProfile:
    """Loads and caches a FacilityProfile from config/facilities/<facility_id>.yaml."""
    if facility_id in FACILITY_CACHE:
        return FACILITY_CACHE[facility_id]

    fdir = get_facilities_dir()
    yaml_path = fdir / f"{facility_id}.yaml"
    if not yaml_path.exists():
        yaml_path = fdir / f"{facility_id}.yml"

    if not yaml_path.exists():
        # Fallback to default community hospital profile
        default_profile = FacilityProfile(
            facility_id="community_hospital",
            facility_name="Community General Hospital",
            tier="Level 3 Emergency Department",
        )
        FACILITY_CACHE[facility_id] = default_profile
        return default_profile

    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    parsed = _parse_simple_yaml(content)
    # Ensure safe_wait_thresholds_minutes keys are integers
    if "safe_wait_thresholds_minutes" in parsed and isinstance(parsed["safe_wait_thresholds_minutes"], dict):
        parsed["safe_wait_thresholds_minutes"] = {
            int(k): int(v) for k, v in parsed["safe_wait_thresholds_minutes"].items()
        }

    profile = FacilityProfile(**parsed)
    FACILITY_CACHE[facility_id] = profile
    return profile
