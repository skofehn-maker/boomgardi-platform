/*
 * Persian (Jalali / Shamsi) calendar helpers.
 *
 * Presentation only: the API, the database and the Postgres exclusion
 * constraint keep using Gregorian calendar dates (YYYY-MM-DD). This module
 * converts at the UI boundary, so it is loaded from the same origin — no CDN,
 * no build step. See docs/adr/0008-jalali-dates-in-the-presentation-layer.md.
 *
 * The arithmetic 33-year-cycle conversion is the widely used JDF algorithm; it
 * is accurate for 1178-1633 Jalali (roughly 1799-2256).
 */
(function (global) {
    'use strict';

    var FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    var MONTHS = [
        'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
    ];
    var WEEKDAYS = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];

    function div(a, b) {
        return Math.trunc(a / b);
    }

    function pad2(value) {
        return value < 10 ? '0' + value : String(value);
    }

    // 1403 → '۱۴۰۳'
    function faDigits(value) {
        return String(value).replace(/[0-9]/g, function (digit) {
            return FA_DIGITS[Number(digit)];
        });
    }

    // Gregorian (gy, gm, gd) → {jy, jm, jd}
    function toJalali(gy, gm, gd) {
        var gDaysInMonth = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
        var jy = gy <= 1600 ? 0 : 979;
        var y = gy <= 1600 ? gy - 621 : gy - 1600;
        var y2 = gm > 2 ? y + 1 : y;

        var days = (365 * y)
            + div(y2 + 3, 4)
            - div(y2 + 99, 100)
            + div(y2 + 399, 400)
            - 80
            + gd
            + gDaysInMonth[gm - 1];

        jy += 33 * div(days, 12053);
        days %= 12053;
        jy += 4 * div(days, 1461);
        days %= 1461;

        if (days > 365) {
            jy += div(days - 1, 365);
            days = (days - 1) % 365;
        }

        var jm = days < 186 ? 1 + div(days, 31) : 7 + div(days - 186, 30);
        var jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);

        return { jy: jy, jm: jm, jd: jd };
    }

    // Jalali (jy, jm, jd) → {gy, gm, gd}
    function toGregorian(jy, jm, jd) {
        var gy = jy <= 979 ? 621 : 1600;
        var y = jy <= 979 ? jy : jy - 979;

        var days = (365 * y)
            + (div(y, 33) * 8)
            + div((y % 33) + 3, 4)
            + 78
            + jd
            + (jm < 7 ? (jm - 1) * 31 : ((jm - 7) * 30) + 186);

        gy += 400 * div(days, 146097);
        days %= 146097;

        if (days > 36524) {
            days -= 1;
            gy += 100 * div(days, 36524);
            days %= 36524;
            if (days >= 365) {
                days += 1;
            }
        }

        gy += 4 * div(days, 1461);
        days %= 1461;

        if (days > 365) {
            gy += div(days - 1, 365);
            days = (days - 1) % 365;
        }

        var gd = days + 1;
        var isLeap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
        var gMonthLength = [0, 31, isLeap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        var gm = 1;

        while (gm <= 12 && gd > gMonthLength[gm]) {
            gd -= gMonthLength[gm];
            gm += 1;
        }

        return { gy: gy, gm: gm, gd: gd };
    }

    // Anything date-like ('2024-11-25', '2024-11-25T00:00:00Z') → 'YYYY-MM-DD'.
    function isoPart(value) {
        if (!value) {
            return '';
        }
        var match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return match ? match[0] : '';
    }

    function toJalaliFromIso(value) {
        var iso = isoPart(value);
        if (!iso) {
            return null;
        }
        return toJalali(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)), Number(iso.slice(8, 10)));
    }

    // Jalali parts → the Gregorian 'YYYY-MM-DD' that the API expects.
    function toIso(jy, jm, jd) {
        var g = toGregorian(jy, jm, jd);
        return String(g.gy) + '-' + pad2(g.gm) + '-' + pad2(g.gd);
    }

    // '2024-11-25' → '۱۴۰۳/۰۹/۰۵'
    function format(value) {
        var parts = toJalaliFromIso(value);
        if (!parts) {
            return '';
        }
        return faDigits(parts.jy) + '/' + faDigits(pad2(parts.jm)) + '/' + faDigits(pad2(parts.jd));
    }

    // '2024-11-25' → '۲۵ آذر ۱۴۰۳' (used where a month name reads better).
    function formatLong(value) {
        var parts = toJalaliFromIso(value);
        if (!parts) {
            return '';
        }
        return faDigits(parts.jd) + ' ' + MONTHS[parts.jm - 1] + ' ' + faDigits(parts.jy);
    }

    function monthLabel(jy, jm) {
        return MONTHS[jm - 1] + ' ' + faDigits(jy);
    }

    function isLeapJalali(jy) {
        // Esfand has 30 days only in a leap year; the round trip is the probe.
        var g = toGregorian(jy, 12, 30);
        return toJalali(g.gy, g.gm, g.gd).jm === 12;
    }

    function monthLength(jy, jm) {
        if (jm <= 6) {
            return 31;
        }
        if (jm <= 11) {
            return 30;
        }
        return isLeapJalali(jy) ? 30 : 29;
    }

    // Saturday-first column index for a Jalali month's first day.
    function weekdayOffset(jy, jm) {
        var iso = toIso(jy, jm, 1);
        var dow = new Date(iso + 'T00:00:00Z').getUTCDay(); // 0 = Sunday
        return (dow + 1) % 7;
    }

    function todayIso() {
        var now = new Date();
        return String(now.getFullYear()) + '-'
            + pad2(now.getMonth() + 1) + '-'
            + pad2(now.getDate());
    }

    function todayJalali() {
        return toJalaliFromIso(todayIso());
    }

    global.JalaliDate = {
        FA_DIGITS: FA_DIGITS,
        MONTHS: MONTHS,
        WEEKDAYS: WEEKDAYS,
        faDigits: faDigits,
        toJalali: toJalali,
        toGregorian: toGregorian,
        toJalaliFromIso: toJalaliFromIso,
        toIso: toIso,
        format: format,
        formatLong: formatLong,
        monthLabel: monthLabel,
        isLeapJalali: isLeapJalali,
        monthLength: monthLength,
        weekdayOffset: weekdayOffset,
        todayIso: todayIso,
        todayJalali: todayJalali
    };
})(window);
