from datetime import datetime

from pydantic import BaseModel


class EnrollmentResponse(BaseModel):
    enrollment_id: int
    batch_id: int
    created_at: datetime



# Repository

import os
import httpx

from app.interfaces.enrollment_response import EnrollmentResponse

LEDGER_URL = os.environ["LEDGER_URL"]


async def get_enrollments_from_ledger(start_date, end_date):
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{LEDGER_URL.rstrip('/')}/enrollments/",
            params=params,
        )
        response.raise_for_status()

    return [
        EnrollmentResponse.model_validate(item)
        for item in response.json()
    ]


#service

from datetime import datetime

from app.repositories.ledger_repository import (
    get_enrollments_from_ledger,
)
from app.interfaces.enrollment_response import EnrollmentResponse


async def fetch_enrollments(
    start_date: datetime,
    end_date: datetime,
) -> list[EnrollmentResponse]:
    return await get_enrollments_from_ledger(
        start_date=start_date,
        end_date=end_date,
    )


from datetime import date, datetime, time, timedelta, timezone

from app.services.enrollment_service import fetch_enrollments


async def get_enrollment_insights(
    start_date: date,
    end_date: date,
):
    if start_date > end_date:
        raise ValueError(
            "start_date must be before or equal to end_date"
        )

    # Inclusive date range, using UTC boundaries.
    start_dt = datetime.combine(
        start_date, time.min, tzinfo=timezone.utc
    )
    end_dt = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )

    enrollments = await fetch_enrollments(
        start_date=start_dt,
        end_date=end_dt,
    )

    total_seconds = (end_dt - start_dt).total_seconds()
    bucket_seconds = total_seconds / 7

    counts = [0] * 7
    labels = []

    for i in range(7):
        bucket_start = start_dt + timedelta(
            seconds=i * bucket_seconds
        )
        bucket_end = start_dt + timedelta(
            seconds=(i + 1) * bucket_seconds
        )

        # Display inclusive-looking date labels.
        last_instant = bucket_end - timedelta(microseconds=1)

        labels.append(
            f"{bucket_start:%b %d}–{last_instant:%b %d}"
        )

    for enrollment in enrollments:
        created_at = enrollment.created_at

        # Treat naive timestamps as UTC; normalize aware ones to UTC.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)

        if not start_dt <= created_at < end_dt:
            continue

        index = int(
            (created_at - start_dt).total_seconds()
            / bucket_seconds
        )

        # Protect against floating-point boundary effects.
        index = min(max(index, 0), 6)
        counts[index] += 1

    return {
        "success": True,
        "chart": {
            "title": "Enrollment Trend",
            "type": "line",
            "x_axis": {
                "label": "Date",
                "data": labels,
            },
            "y_axis": {
                "label": "Number of Enrollments",
                "data": counts,
            },
        },
        "total_enrollments": len(enrollments),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


# Routes

from datetime import date

from fastapi import APIRouter, HTTPException, Query
import httpx

from app.insights import get_enrollment_insights

router = APIRouter(
    prefix="/insights",
    tags=["Insights"],
)


@router.get("/enrollments")
async def enrollment_chart(
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    try:
        return await get_enrollment_insights(
            start_date=start_date,
            end_date=end_date,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch enrollment data from Ledger",
        ) from exc


    
#main.property

from fastapi import FastAPI

from app.routes.insights import router as insights_router

app = FastAPI(title="Analytics Service")

app.include_router(insights_router)


@app.get("/health")
async def health_check():
    return {
        "success": True,
        "service": "insights",
        "status": "healthy",
    }