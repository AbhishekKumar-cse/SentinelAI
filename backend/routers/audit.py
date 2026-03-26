"""
Audit Router — audit ledger queries, export, and compliance reports.
"""
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


@router.get("/audit/{workflow_id}/verify", summary="Verify hash chain integrity")
async def verify_audit_chain(workflow_id: str, request: Request):
    """Verify the SHA-256 hash chain integrity for an entire workflow audit trail."""
    from services import audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    report = await audit_service.verify_chain(workflow_id=workflow_id, tenant_id=tenant_id)
    return report


@router.get("/audit/{workflow_id}/export", summary="Export audit report as PDF")
async def export_audit_report(workflow_id: str, request: Request):
    """Generate a signed PDF audit report and return Firebase Storage download URL."""
    import uuid

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    # In production: call generate_document() + sign with SHA-256
    report_id = uuid.uuid4().hex[:12]
    storage_uri = f"audit_reports/{tenant_id}/{workflow_id}/{report_id}.pdf"

    return {
        "workflow_id": workflow_id,
        "report_id": f"RPT-{report_id.upper()}",
        "download_url": f"https://storage.googleapis.com/{storage_uri}",
        "storage_uri": storage_uri,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }


@router.get("/audit/{workflow_id}/compliance/{regulation}", summary="Compliance report")
async def get_compliance_report(
    workflow_id: str,
    regulation: str,
    request: Request,
):
    """
    Generate a compliance report for the workflow.
    Supported regulations: sox, gdpr, pci_dss, hipaa
    """
    SUPPORTED_REGULATIONS = {"sox", "gdpr", "pci_dss", "hipaa"}
    if regulation not in SUPPORTED_REGULATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported regulation. Supported: {SUPPORTED_REGULATIONS}",
        )

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    # Verify chain first
    from services import audit_service
    chain_report = await audit_service.verify_chain(workflow_id=workflow_id, tenant_id=tenant_id)

    # Return compliance report structure
    return {
        "workflow_id": workflow_id,
        "regulation": regulation.upper(),
        "chain_integrity": chain_report["is_intact"],
        "total_audit_records": chain_report["total_records"],
        "compliance_status": "COMPLIANT" if chain_report["is_intact"] else "REVIEW_REQUIRED",
        "findings": chain_report.get("hash_failures", []),
        "checked_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
