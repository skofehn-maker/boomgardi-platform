"""Listing endpoints.

``POST /api/v1/listings`` lets an authenticated user create a listing as its host.
``GET /api/v1/listings`` is public and only ever returns published listings.
``GET /api/v1/listings/admin`` is the admin-only view of every listing.
``GET /api/v1/listings/mine`` lists the caller's own listings, drafts included.
``PATCH /api/v1/listings/{id}/publish`` lets the owning host publish a draft.
``POST /api/v1/listings/{id}/rooms`` adds a room as the owning host.
``GET /api/v1/listings/{id}`` is the public detail of one published listing.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.models.listing import Listing, Room
from app.models.user import User
from app.schemas.listing import (
    ListingCreate,
    ListingResponse,
    RoomCreate,
    RoomResponse,
)

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
    "/mine",
    response_model=list[ListingResponse],
    summary="List the current user's own listings (drafts included)",
)
async def list_my_listings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Listing]:
    """Every listing hosted by the caller; never another host's rows."""
    result = await db.scalars(
        select(Listing)
        .where(Listing.host_id == current_user.id)
        .order_by(Listing.created_at.desc())
    )
    return list(result.all())


@router.patch(
    "/{listing_id}/publish",
    response_model=ListingResponse,
    summary="Publish one of the current user's draft listings",
)
async def publish_listing(
    listing_id: uuid.UUID,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per publish attempt; replaying it is a no-op.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Listing:
    """Move ``draft`` -> ``published`` for the owning host (ADR 0004)."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="اقامتگاه یافت نشد"
        )
    if listing.host_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط میزبان این اقامتگاه می‌تواند آن را منتشر کند",
        )
    if listing.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="اقامتگاه بایگانی‌شده قابل انتشار نیست",
        )

    # Publishing an already published listing writes nothing: the transition is
    # the same target status, which is what makes a replayed key safe.
    if listing.status != "published":
        listing.status = "published"
        await db.commit()

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


@router.post(
    "/{listing_id}/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a room to a listing as its host",
)
async def add_room(
    listing_id: uuid.UUID,
    payload: RoomCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per create attempt; a replay returns the original room.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Room:
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="اقامتگاه یافت نشد"
        )
    if listing.host_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط میزبان این اقامتگاه می‌تواند اتاق اضافه کند",
        )

    existing = await db.scalar(
        select(Room).where(
            Room.listing_id == listing_id,
            Room.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    room = Room(
        listing_id=listing_id, idempotency_key=idempotency_key, **payload.model_dump()
    )
    db.add(room)

    try:
        await db.commit()
    except IntegrityError:
        # A concurrent retry with the same key won the race: return that room.
        await db.rollback()
        duplicate = await db.scalar(
            select(Room).where(
                Room.listing_id == listing_id,
                Room.idempotency_key == idempotency_key,
            )
        )
        if duplicate is None:
            raise
        return duplicate

    await db.refresh(room)
    return room


@router.get(
    "",
    response_model=list[ListingResponse],
    summary="List published listings",
)
async def list_published_listings(
    city: str | None = Query(default=None, description="Filter by city (substring, case-insensitive)"),
    max_price: float | None = Query(default=None, description="Only listings with a room priced at most this much"),
    db: AsyncSession = Depends(get_db),
) -> list[Listing]:
    stmt = select(Listing).where(Listing.status == "published")
    if city:
        stmt = stmt.where(Listing.city.ilike(f"%{city}%"))
    if max_price is not None:
        stmt = stmt.where(
            Listing.id.in_(
                select(Room.listing_id).where(Room.price_per_night <= max_price)
            )
        )
    stmt = stmt.order_by(Listing.created_at.desc())
    result = await db.scalars(stmt)
    return list(result.all())


@router.get(
    "/{listing_id}",
    response_model=ListingResponse,
    summary="Public detail of one published listing",
)
async def get_published_listing(
    listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Listing:
    """Declared after ``/mine`` and ``/admin`` so those literal paths win."""
    listing = await db.scalar(
        select(Listing).where(
            Listing.id == listing_id, Listing.status == "published"
        )
    )
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="اقامتگاه یافت نشد"
        )
    return listing
