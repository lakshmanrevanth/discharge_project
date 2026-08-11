"""Extraction result models (SSoT §5.2, §6.1 Table 3).

Canonical shapes the Clinical Extractor produces for ANY patient_id
(no hard-coded sample patients).

Conflict §16 row 1 — BOTH naming sets live on DischargeExtraction:
  FA5 Table 3:        doctors, adr_allergy_info, follow_up_appointments
  rules.yaml:         attending_physician, consulting_doctors, allergies,
                      follow_up_appointment
After extraction, call fill_fa5_and_rules_aliases() so both sides are filled
when either side has data — Completeness can check either name.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PrescriptionItem(BaseModel):
    """One row of FA5 Table 3 'Prescription (per med)'."""

    sl_no: int | None = None
    medicine_name: str
    strength: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None
    period: str | None = None
    remarks: str | None = None
    total_quantity: str | None = None


class LabTestResult(BaseModel):
    """One row from a lab report's results table."""

    test_name: str
    result: str | None = None
    units: str | None = None
    reference_range: str | None = None
    flag: str | None = Field(default=None, description="e.g. NORMAL, HIGH, LOW")


class BillLineItem(BaseModel):
    """One row of a hospital bill's line items."""

    description: str
    item_code: str | None = None
    qty: float | None = None
    unit_price: float | None = None
    total: float | None = None


class DischargeExtraction(BaseModel):
    """Structured discharge report — rules.yaml names + FA5 Table 3 aliases."""

    patient_id: str | None = None
    patient_name: str | None = None
    age: int | None = None
    gender: str | None = None
    address: str | None = None
    admission_date: str | None = None
    discharge_date: str | None = None
    ward: str | None = None
    bed_no: str | None = None

    # rules.yaml names (granular)
    attending_physician: str | None = None
    consulting_doctors: list[str] = Field(default_factory=list)
    discharge_diagnosis: list[str] = Field(default_factory=list)
    medications: list[PrescriptionItem] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    follow_up_appointment: str | None = None
    discharge_instructions: str | None = None
    discharge_approved: bool | None = None
    discharge_approved_by: str | None = None

    # FA5 Table 3 names (aliases — must stay on the schema, §16 row 1)
    doctors: list[str] = Field(
        default_factory=list,
        description="FA5 alias for attending_physician + consulting_doctors",
    )
    adr_allergy_info: list[str] = Field(
        default_factory=list,
        description="FA5 alias for allergies",
    )
    follow_up_appointments: str | None = Field(
        default=None,
        description="FA5 alias for follow_up_appointment",
    )

    language: str = Field(default="en", description="Source document language code")


class LabExtraction(BaseModel):
    """Structured lab report fields (FA5 Table 3 'Lab Report')."""

    patient_id: str | None = None
    vendor_name: str | None = None
    lab_name: str | None = None
    report_date: str | None = None
    tests: list[LabTestResult] = Field(default_factory=list)
    language: str = Field(default="en", description="Source document language code")


class BillExtraction(BaseModel):
    """Structured bill fields (FA5 Table 3 'Bill')."""

    patient_id: str | None = None
    hospital_name: str | None = None
    billing_date: str | None = None
    line_items: list[BillLineItem] = Field(default_factory=list)
    total_amount: float | None = None
    payment_status: str | None = None
    language: str = Field(default="en", description="Source document language code")


class ExtractionResult(BaseModel):
    """Everything the Extractor produces for one patient case.

    Works for any patient_id that has files under data/input/ — not limited
    to the sample corpus (P1019–P1024).
    """

    patient_id: str
    discharge: DischargeExtraction | None = None
    lab: LabExtraction | None = None
    bill: BillExtraction | None = None
    source_files: dict[str, str] = Field(default_factory=dict)
    # Which MCP Resources were read (uri -> short note / length)
    resources_used: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def fill_fa5_and_rules_aliases(discharge: DischargeExtraction) -> DischargeExtraction:
    """Fill missing FA5 aliases from rules.yaml fields, and the other way around.

    Call this after every successful discharge extraction so both naming sets
    are always present for Completeness / HITL later.
    """
    # rules.yaml → FA5
    if not discharge.doctors:
        doctors: list[str] = []
        if discharge.attending_physician:
            doctors.append(discharge.attending_physician)
        doctors.extend(discharge.consulting_doctors or [])
        discharge.doctors = doctors

    if not discharge.adr_allergy_info and discharge.allergies:
        discharge.adr_allergy_info = list(discharge.allergies)

    if not discharge.follow_up_appointments and discharge.follow_up_appointment:
        discharge.follow_up_appointments = discharge.follow_up_appointment

    # FA5 → rules.yaml (if the LLM / source filled only FA5 names)
    if not discharge.allergies and discharge.adr_allergy_info:
        discharge.allergies = list(discharge.adr_allergy_info)

    if not discharge.follow_up_appointment and discharge.follow_up_appointments:
        discharge.follow_up_appointment = discharge.follow_up_appointments

    if not discharge.attending_physician and not discharge.consulting_doctors and discharge.doctors:
        # First name → attending; rest → consulting (simple, beginner-friendly)
        discharge.attending_physician = discharge.doctors[0]
        discharge.consulting_doctors = list(discharge.doctors[1:])

    return discharge
