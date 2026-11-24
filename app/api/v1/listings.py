"""Listing endpoints.

``POST /api/v1/listings`` lets an authenticated user create a listing as its host.
``GET /api/v1/listings`` is public and only ever returns published listings.
``GET /api/v1/listings/admin`` is the admin-only view of every listing.
"""

import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.models.listing import Listing
from app.models.user import User
from app.schemas.listing import ListingCreate, ListingResponse

router = APIRouter()


async def _load_listing(db: AsyncSession, listing_id: uuid.UUID) -> Listing:
    """Re-read a listing so the eagerly loaded ``rooms`` collection is populated."""
    result = await db.execute(
        select(Listing)
        .where(Listing.id == listing_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a listing as the current user (draft)",
)
async def create_listing(
    payload: ListingCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per create attempt; a replay returns the original listing.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Listing:
    existing = await db.scalar(
        select(Listing).where(
            Listing.host_id == current_user.id,
            Listing.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return await _load_listing(db, existing.id)

    listing = Listing(
        host_id=current_user.id,
        idempotency_key=idempotency_key,
        status="draft",
        **payload.model_dump(),
    )
    db.add(listing)

    try:
        await db.commit()
    except IntegrityError:
        # A concurrent retry with the same key won the race: return that listing.
        await db.rollback()
        duplicate = await db.scalar(
            select(Listing).where(
                Listing.host_id == current_user.id,
                Listing.idempotency_key == idempotency_key,
            )
        )
        if duplicate is None:
            raise
        return await _load_listing(db, duplicate.id)

    return await _load_listing(db, listing.id)


@router.get(
    "/admin",
    response_model=list[ListingResponse],
    summary="List every listing, whatever its status (admin only)",
)
async def list_all_listings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[Listing]:
    """Admin read path: drafts, published and archived listings alike (ADR 0003)."""
    result = await db.scalars(
        select(Listing).order_by(Listing.created_at.desc())
    )
    return list(result.all())


@router.get(
    "",
    response_model=list[ListingResponse],
    summary="List published listings",
)
async def list_published_listings(db: AsyncSession = Depends(get_db)) -> list[Listing]:
    result = await db.scalars(
        select(Listing)
        .where(Listing.status == "published")
        .order_by(Listing.created_at.desc())
    )
    return list(result.all())
