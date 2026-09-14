# src/database/medplum_seed.py
"""Seed a Medplum project with the FHIR data the agent expects.

Mirrors the old database/seed.sql (St. Mary Health Network) as FHIR R4:
  * 1 Organization  — the network (the tenant/compartment)
  * 2 Locations     — St. Mary Medical Center (SMMC), Downtown General (DGH)
  * 3 Practitioners + PractitionerRoles (specialty + practitioner + location)
  * 3 Schedules     — actor = [Practitioner, Location]
  * ~14 days of free Slots per doctor from their weekly windows
  * 1 Patient       — John Doe, +15550192834
  * 1 Questionnaire — Cardiology Pre-visit Intake (Dr. Rao)

Everything is one FHIR **transaction Bundle** with per-resource conditional
creates (`ifNoneExist` on a seed identifier), so re-running is idempotent and
intra-bundle references resolve via urn:uuid fullUrls.

Run:
    uv run python -m src.database.medplum_seed --dry-run     # build + inspect only
    uv run python -m src.database.medplum_seed               # POST to Medplum
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

SEED_SYSTEM = "https://ai-prof.example/seed"
TZ = ZoneInfo("America/New_York")
DAYS_AHEAD = 14
SLOT_MINUTES = 30

# doctor key -> (given, family, specialty, snomed_code, location_key, [(weekday, start, end)])
DOCTORS = {
    "doc-sharma": ("Aarav", "Sharma", "Dermatology", "394582007", "SMMC",
                   [("Monday", "09:00", "12:00"), ("Friday", "13:00", "17:00")]),
    "doc-rao": ("Priya", "Rao", "Cardiology", "394579002", "SMMC",
                [("Thursday", "13:00", "17:00"), ("Friday", "09:00", "12:00")]),
    "doc-jenkins": ("Sarah", "Jenkins", "Orthopedics", "394801008", "DGH",
                    [("Wednesday", "09:00", "12:00"), ("Thursday", "13:00", "17:00")]),
}
LOCATIONS = {
    "SMMC": "St. Mary Medical Center",
    "DGH": "Downtown General Hospital",
}
NETWORK_KEY = "st-mary-network"
NETWORK_NAME = "St. Mary Health Network"


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


class _Bundle:
    """Accumulates transaction entries; each resource gets a urn:uuid fullUrl
    (for intra-bundle references) and a conditional-create request."""

    def __init__(self) -> None:
        self.entries: list = []
        self.urn: dict = {}  # seed-value -> urn:uuid

    def add(self, seed_value: str, resource: dict) -> str:
        ref = self.urn.get(seed_value)
        if ref:
            return ref
        ref = f"urn:uuid:{uuid.uuid4()}"
        self.urn[seed_value] = ref
        resource.setdefault("identifier", [{"system": SEED_SYSTEM, "value": seed_value}])
        self.entries.append({
            "fullUrl": ref,
            "resource": resource,
            "request": {
                "method": "POST",
                "url": resource["resourceType"],
                "ifNoneExist": f"identifier={SEED_SYSTEM}|{seed_value}",
            },
        })
        return ref

    def bundle(self) -> dict:
        return {"resourceType": "Bundle", "type": "transaction", "entry": self.entries}


def _slot_times(weekday: str, start_hhmm: str, end_hhmm: str):
    """Yield (start_dt, end_dt) for each SLOT_MINUTES block on matching weekdays
    within the next DAYS_AHEAD days."""
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    today = datetime.now(TZ).date()
    for offset in range(DAYS_AHEAD):
        day = today + timedelta(days=offset)
        if day.strftime("%A") != weekday:
            continue
        cursor = datetime.combine(day, time(sh, sm), tzinfo=TZ)
        window_end = datetime.combine(day, time(eh, em), tzinfo=TZ)
        while cursor + timedelta(minutes=SLOT_MINUTES) <= window_end:
            nxt = cursor + timedelta(minutes=SLOT_MINUTES)
            yield cursor, nxt
            cursor = nxt


def build_bundle() -> dict:
    b = _Bundle()

    network = b.add(NETWORK_KEY, {"resourceType": "Organization", "name": NETWORK_NAME, "active": True})

    location_refs = {}
    for key, name in LOCATIONS.items():
        location_refs[key] = b.add(key, {
            "resourceType": "Location",
            "name": name,
            "status": "active",
            "managingOrganization": {"reference": network},
        })

    # Patient — John Doe, managed by the network (the compartment).
    b.add("pat-john-doe", {
        "resourceType": "Patient",
        "name": [{"given": ["John"], "family": "Doe"}],
        "telecom": [{"system": "phone", "value": "+15550192834", "use": "mobile"}],
        "birthDate": "1985-04-12",
        "managingOrganization": {"reference": network},
    })

    for key, (given, family, specialty, snomed, loc_key, windows) in DOCTORS.items():
        prac = b.add(key, {
            "resourceType": "Practitioner",
            "active": True,
            "name": [{"given": [given], "family": family, "prefix": ["Dr."]}],
        })
        specialty_cc = {
            "coding": [{"system": "http://snomed.info/sct", "code": snomed, "display": specialty}],
            "text": specialty,
        }
        b.add(f"role-{key}", {
            "resourceType": "PractitionerRole",
            "active": True,
            "practitioner": {"reference": prac},
            "organization": {"reference": network},
            "location": [{"reference": location_refs[loc_key]}],
            "specialty": [specialty_cc],
        })
        schedule = b.add(f"sched-{key}", {
            "resourceType": "Schedule",
            "active": True,
            "actor": [{"reference": prac}, {"reference": location_refs[loc_key]}],
        })
        for weekday, start_hhmm, end_hhmm in windows:
            for start_dt, end_dt in _slot_times(weekday, start_hhmm, end_hhmm):
                iso = start_dt.isoformat()
                b.add(f"slot-{key}-{iso}", {
                    "resourceType": "Slot",
                    "schedule": {"reference": schedule},
                    "status": "free",
                    "start": iso,
                    "end": end_dt.isoformat(),
                })

    # Cardiology pre-visit questionnaire (matched to Dr. Rao by specialty text).
    b.add("q-cardiology-previsit", {
        "resourceType": "Questionnaire",
        "status": "active",
        "name": "CardiologyPreVisitIntake",
        "title": "Cardiology Pre-visit Intake",
        "useContext": [{
            "code": {"system": "http://terminology.hl7.org/CodeSystem/usage-context-type", "code": "focus"},
            "valueCodeableConcept": {
                "coding": [{"system": "http://snomed.info/sct", "code": "394579002", "display": "Cardiology"}],
                "text": "Cardiology",
            },
        }],
        "item": [
            {"linkId": "q1", "text": "Are you experiencing chest pain?", "type": "boolean", "required": True},
            {"linkId": "q2", "text": "How long have you had symptoms?", "type": "string", "required": True},
            {"linkId": "q3", "text": "Do you have a family history of heart disease?", "type": "boolean", "required": False},
        ],
    })

    return b.bundle()


def _summarize(bundle: dict) -> None:
    counts: dict = {}
    for entry in bundle["entry"]:
        rt = entry["resource"]["resourceType"]
        counts[rt] = counts.get(rt, 0) + 1
    print("Transaction bundle:")
    for rt, n in sorted(counts.items()):
        print(f"  {rt:16} {n}")
    print(f"  {'TOTAL':16} {len(bundle['entry'])}")


async def _run(dry_run: bool) -> None:
    bundle = build_bundle()
    _summarize(bundle)

    if dry_run:
        sample = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Slot")
        print("\nSample Slot resource:")
        print(json.dumps(sample, indent=2))
        print("\n(dry-run: nothing sent to Medplum)")
        return

    from src.database.medplum_client import get_medplum_client
    medplum = get_medplum_client()
    if not medplum:
        print("Medplum not configured (set MEDPLUM_CLIENT_ID/SECRET). Aborting.")
        return

    result = await medplum.transaction(bundle)
    created = sum(
        1 for e in result.get("entry", [])
        if str((e.get("response") or {}).get("status", "")).startswith(("200", "201"))
    )
    print(f"\nMedplum transaction complete: {created}/{len(bundle['entry'])} entries OK.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Medplum with FHIR scheduling data")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the bundle without sending")
    args = parser.parse_args()
    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
