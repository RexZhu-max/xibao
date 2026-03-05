from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import MAX_UPLOAD_BYTES, POSTER_DIR, UPLOAD_DIR
from app.db import (
    create_employee,
    create_import_batch,
    create_performance,
    delete_employee,
    delete_performance,
    get_daily_ranking,
    init_db,
    list_employees,
    list_performances,
    update_employee,
    update_performance,
    upsert_daily_records,
)
from app.services.ocr_service import OCRError, parse_sales_board
from app.services.poster_service import generate_top3_posters

STATIC_DIR = Path(__file__).resolve().parent / "static"


class RecordIn(BaseModel):
    employee_name: str = Field(min_length=1, max_length=64)
    deal_count: int = Field(ge=0)
    high_intent_count: int = Field(ge=0)
    private_domain_new: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ManualSubmitRequest(BaseModel):
    report_date: str
    records: list[RecordIn]


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class PerformanceIn(BaseModel):
    employee_id: int = Field(ge=1)
    report_date: str
    deal_count: int = Field(ge=0)
    high_intent_count: int = Field(ge=0)
    private_domain_new: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


def _raise_http_from_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def build_summary(report_date: str) -> dict[str, Any]:
    ranking = get_daily_ranking(report_date)
    champion = ranking[0] if ranking else None
    top_three = ranking[:3]
    posters = generate_top3_posters(report_date, top_three) if top_three else []

    return {
        "report_date": report_date,
        "champion": champion,
        "ranking": ranking,
        "top_three": top_three,
        "posters": posters,
    }


def build_dashboard(report_date: str) -> dict[str, Any]:
    summary = build_summary(report_date)
    ranking = summary["ranking"]

    total_deal = sum(item["deal_count"] for item in ranking)
    total_high_intent = sum(item["high_intent_count"] for item in ranking)
    total_private_domain = sum(item["private_domain_new"] for item in ranking)

    return {
        "report_date": report_date,
        "staff_count": len(ranking),
        "total_deal": total_deal,
        "total_high_intent": total_high_intent,
        "total_private_domain": total_private_domain,
        "champion": summary["champion"],
        "top_three": summary["top_three"],
    }


app = FastAPI(title="销售日报运营系统", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard")
def get_dashboard(report_date: str | None = None) -> dict[str, Any]:
    final_date = report_date or date.today().isoformat()
    return build_dashboard(final_date)


@app.get("/api/employees")
def get_employees(keyword: str | None = None) -> dict[str, Any]:
    return {"items": list_employees(keyword=keyword)}


@app.post("/api/employees")
def add_employee(payload: EmployeeIn) -> dict[str, Any]:
    try:
        employee = create_employee(payload.name)
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return employee


@app.put("/api/employees/{employee_id}")
def edit_employee(employee_id: int, payload: EmployeeIn) -> dict[str, Any]:
    try:
        employee = update_employee(employee_id, payload.name)
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return employee


@app.delete("/api/employees/{employee_id}")
def remove_employee(employee_id: int) -> dict[str, str]:
    try:
        delete_employee(employee_id)
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return {"status": "ok"}


@app.get("/api/performances")
def get_performances(report_date: str | None = None, employee_id: int | None = None) -> dict[str, Any]:
    return {"items": list_performances(report_date=report_date, employee_id=employee_id)}


@app.post("/api/performances")
def add_performance(payload: PerformanceIn) -> dict[str, Any]:
    try:
        created = create_performance(payload.model_dump())
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return created


@app.put("/api/performances/{performance_id}")
def edit_performance(performance_id: int, payload: PerformanceIn) -> dict[str, Any]:
    try:
        updated = update_performance(performance_id, payload.model_dump())
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return updated


@app.delete("/api/performances/{performance_id}")
def remove_performance(performance_id: int) -> dict[str, str]:
    try:
        delete_performance(performance_id)
    except (ValueError, LookupError) as exc:
        _raise_http_from_error(exc)
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_daily_board(file: UploadFile = File(...), report_date: str | None = None) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"上传图片过大，请控制在 {MAX_UPLOAD_BYTES // 1000000}MB 以内后重试",
        )

    ext = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    filename = f"{date.today().isoformat()}_{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    save_path.write_bytes(content)

    mime_type = file.content_type or "image/jpeg"

    try:
        parsed = parse_sales_board(content, mime_type)
        actual_report_date = report_date or parsed["report_date"]
        payload = {"report_date": actual_report_date, "records": parsed["records"]}

        batch_id = create_import_batch(
            report_date=actual_report_date,
            source_image=str(save_path),
            raw_payload=payload,
            status="parsed",
        )
        upsert_daily_records(actual_report_date, payload["records"], source_batch_id=batch_id)

        summary = build_summary(actual_report_date)
        summary.update(
            {
                "batch_id": batch_id,
                "source_image": f"/static/uploads/{filename}",
                "parsed_records": payload["records"],
            }
        )
        return summary
    except OCRError as exc:
        actual_report_date = report_date or date.today().isoformat()
        create_import_batch(
            report_date=actual_report_date,
            source_image=str(save_path),
            raw_payload={"error": str(exc)},
            status="failed",
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/manual-submit")
def manual_submit(payload: ManualSubmitRequest) -> dict[str, Any]:
    records = [item.model_dump() for item in payload.records]
    upsert_daily_records(payload.report_date, records, source_batch_id=None)
    return build_summary(payload.report_date)


@app.get("/api/ranking")
def get_ranking(report_date: str | None = None) -> dict[str, Any]:
    final_date = report_date or date.today().isoformat()
    return build_summary(final_date)


app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")
app.mount("/static/posters", StaticFiles(directory=str(POSTER_DIR)), name="posters")
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
