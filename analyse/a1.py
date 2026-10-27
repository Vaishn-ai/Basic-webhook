#Response Model

# ledger/app/interfaces/enrollment_response.py

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel, ConfigDict


class EnrollmentResponse(BaseModel):
    enrollment_id: int
    batch_id: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)

# ledger --> repository

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment import Enrollment


async def get_enrollments(
    db: AsyncSession,
    start_date,
    end_date,
):
    query = (
        select(
            Enrollment.enrollment_id,
            Enrollment.batch_id,
            Enrollment.created_at,
        )
        .where(
            Enrollment.created_at >= start_date,
            Enrollment.created_at < end_date,
        )
        .order_by(Enrollment.created_at)
    )

    result = await db.execute(query)
    return result.mappings().all()


# route

async def list_enrollments(
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await fetch_enrollments(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )

#service

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.enrollment_repository import get_enrollments
from app.interfaces.enrollment_response import EnrollmentResponse
from app.validators import check_date  # Adjust import path to your project


async def fetch_enrollments(
    db: AsyncSession,
    start_date: str,
    end_date: str,
) -> list[EnrollmentResponse]:

    start_date = check_date(start_date)
    end_date = check_date(end_date)

    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be earlier than end_date",
        )

    enrollments = await get_enrollments(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        EnrollmentResponse.model_validate(enrollment)
        for enrollment in enrollments
    ]