"""Phase 8 acceptance tests: Persian (Jalali) dates in the booking UI.

Written before the implementation (Iron Rule 1). These are static/template
checks — the conversion itself is JavaScript, and the API contract must stay
Gregorian `YYYY-MM-DD`.
"""

import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app

JALALI_MODULE = "/static/js/jalali.js"
BOOKING_PAGES = ["/profile", "/host", "/host/bookings", "/profile/bookings"]


def get_page(path: str):
    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get(path)

    return asyncio.run(scenario())


def test_jalali_module_is_served_locally():
    response = get_page(JALALI_MODULE)
    assert response.status_code == 200, response.text
    assert "javascript" in response.headers["content-type"]

    body = response.text
    assert "JalaliDate" in body
    assert "toJalali" in body
    assert "toGregorian" in body
    # Offline requirement: no external asset is referenced by the module.
    assert "http://" not in body
    assert "https://" not in body


def test_listing_page_uses_a_persian_datepicker():
    body = get_page("/listings/259ea61c-357e-4436-95e9-973cd75c17b2").text

    # A native date input follows the browser locale, not the page language.
    assert 'type="date"' not in body

    assert JALALI_MODULE in body
    assert 'id="check-in-calendar"' in body
    assert 'id="check-out-calendar"' in body
    # The Gregorian value the API receives is kept beside the Shamsi label.
    assert 'data-iso=""' in body
    assert "JalaliDate.toIso(" in body
    assert "JalaliDate.format(" in body


def test_booking_pages_display_shamsi_dates():
    for path in BOOKING_PAGES:
        body = get_page(path).text

        assert JALALI_MODULE in body, path
        assert "JalaliDate.format(" in body, path

        # The ICU-dependent date formatting is what printed Gregorian dates.
        assert "Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeZone: 'UTC' })" not in body, path
        # And the hand-rolled parse of a calendar day is gone from the display path.
        assert "String(value) + 'T00:00:00Z'" not in body, path
        assert "value + 'T00:00:00Z'" not in body, path
