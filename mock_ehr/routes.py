"""REST routes for Mock EHR domains (patients, meds, allergies, labs, care plans).

FA5 does not fix exact URL shapes — these are simple and stable for later
EHR Validation Tool calls.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from mock_ehr.seed import ALLERGIES, CARE_PLANS, LABS, MED_ORDERS, PATIENTS

router = APIRouter()


def _require_patient(patient_id: str) -> dict:
    """Return patient row or raise 404."""
    patient = PATIENTS.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
    return patient


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock_ehr"}


@router.get("/patients")
def list_patients() -> dict:
    """List all patient ids (handy for smoke tests)."""
    return {"patient_ids": sorted(PATIENTS.keys()), "count": len(PATIENTS)}


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str) -> dict:
    return _require_patient(patient_id)


@router.get("/patients/{patient_id}/medications")
def get_medications(patient_id: str) -> dict:
    _require_patient(patient_id)
    return {
        "patient_id": patient_id,
        "medications": MED_ORDERS.get(patient_id, []),
    }


@router.get("/patients/{patient_id}/allergies")
def get_allergies(patient_id: str) -> dict:
    _require_patient(patient_id)
    return {
        "patient_id": patient_id,
        "allergies": ALLERGIES.get(patient_id, []),
    }


@router.get("/patients/{patient_id}/labs")
def get_labs(patient_id: str) -> dict:
    _require_patient(patient_id)
    return {
        "patient_id": patient_id,
        "labs": LABS.get(patient_id, []),
    }


@router.get("/patients/{patient_id}/care-plan")
def get_care_plan(patient_id: str) -> dict:
    _require_patient(patient_id)
    care_plan = CARE_PLANS.get(patient_id)
    if care_plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Care plan not found for patient: {patient_id}",
        )
    return {"patient_id": patient_id, "care_plan": care_plan}
