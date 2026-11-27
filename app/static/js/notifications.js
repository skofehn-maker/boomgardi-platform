/*
 * In-app notification bell (phase 14).
 *
 * Fills the element with id="notification-bell" when the visitor holds a valid
 * token: a bell with the unread count and a dropdown of the latest
 * notifications. Opening the dropdown marks them read
 * (PATCH /api/v1/notifications/read) and clears the badge.
 *
 * Messages are rendered with textContent, never innerHTML, so stored text
 * cannot inject markup. The API is always called with the caller's bearer
 * token; no user id is ever supplied by the browser.
 */
(function () {
    'use strict';

    var mount = document.getElementById('notification-bell');
    if (!mount) { return; }

    var AUTH_KEY = 'access_token';
    var token = localStorage.getItem(AUTH_KEY);
    if (!token) {
        mount.hidden = true;
        return;
    }

    mount.hidden = false;
    mount.innerHTML =
        '<button type="button" class="bell-btn" id="bell-toggle" aria-haspopup="true"'
        + ' aria-expanded="false" aria-controls="bell-panel" aria-label="اعلان‌ها">'
        + '<svg fill="none" viewBox="0 0 24 24" stroke-width="1.7" aria-hidden="true">'
        + '<path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"/>'
        + '</svg>'
        + '<span class="bell-count" id="bell-count">۰</span>'
        + '</button>'
        + '<div class="bell-panel" id="bell-panel">'
        + '<p class="bell-head"><span>اعلان‌ها</span><small id="bell-unread-label"></small></p>'
        + '<div class="bell-list" id="bell-list"><p class="bell-empty">در حال بارگذاری…</p></div>'
        + '</div>';

    var toggle = document.getElementById('bell-toggle');
    var panel = document.getElementById('bell-panel');
    var list = document.getElementById('bell-list');
    var count = document.getElementById('bell-count');
    var unreadLabel = document.getElementById('bell-unread-label');

    var faNumber = function (value) {
        return Number(value || 0).toLocaleString('fa-IR');
    };

    function headers(extra) {
        var result = { Accept: 'application/json', Authorization: 'Bearer ' + token };
        if (extra) {
            Object.keys(extra).forEach(function (key) { result[key] = extra[key]; });
        }
        return result;
    }

    function newKey() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }
        return 'notifications-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    }

    function timeLabel(value) {
        if (!value) { return ''; }
        var hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(value);
        var date = new Date(hasZone ? value : value + 'Z');
        if (Number.isNaN(date.getTime())) { return ''; }
        return date.toLocaleString('fa-IR', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran'
        });
    }

    function setCount(value) {
        var total = Number(value || 0);
        if (total > 0) {
            count.textContent = faNumber(total);
            count.classList.add('show');
            unreadLabel.textContent = faNumber(total) + ' خوانده‌نشده';
        } else {
            count.classList.remove('show');
            unreadLabel.textContent = '';
        }
    }

    function renderList(rows) {
        list.textContent = '';

        if (!rows.length) {
            var empty = document.createElement('p');
            empty.className = 'bell-empty';
            empty.textContent = 'اعلان تازه‌ای ندارید.';
            list.appendChild(empty);
            return;
        }

        rows.slice(0, 8).forEach(function (row) {
            var item = document.createElement('div');
            item.className = 'bell-item' + (row.is_read ? '' : ' unread');

            var message = document.createElement('p');
            message.className = 'bell-message';
            message.textContent = row.message || '';

            var time = document.createElement('p');
            time.className = 'bell-time';
            time.textContent = timeLabel(row.created_at);

            item.appendChild(message);
            if (time.textContent) { item.appendChild(time); }
            list.appendChild(item);
        });
    }

    function load() {
        return Promise.all([
            fetch('/api/v1/notifications?limit=8', { headers: headers() }),
            fetch('/api/v1/notifications/unread', { headers: headers() })
        ]).then(function (responses) {
            var latest = responses[0];
            var unread = responses[1];
            if (latest.status === 401 || unread.status === 401) { return null; }
            if (!latest.ok || !unread.ok) { throw new Error('notifications unavailable'); }
            return Promise.all([latest.json(), unread.json()]);
        }).then(function (data) {
            if (!data) { return; }
            renderList(Array.isArray(data[0]) ? data[0] : []);
            setCount(Array.isArray(data[1]) ? data[1].length : 0);
        }).catch(function () {
            list.textContent = '';
            var failed = document.createElement('p');
            failed.className = 'bell-empty';
            failed.textContent = 'دریافت اعلان‌ها ناموفق بود.';
            list.appendChild(failed);
        });
    }

    function close() {
        panel.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', function (event) {
        event.stopPropagation();
        var isOpen = panel.classList.toggle('open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        if (!isOpen) { return; }

        load().then(function () {
            // Opening the dropdown is the user acknowledging what is inside.
            fetch('/api/v1/notifications/read', {
                method: 'PATCH',
                headers: headers({ 'Idempotency-Key': newKey() })
            }).then(function (response) {
                if (!response.ok) { return; }
                setCount(0);
                Array.prototype.forEach.call(
                    list.querySelectorAll('.bell-item.unread'),
                    function (item) { item.classList.remove('unread'); }
                );
            }).catch(function () { /* keep the badge; a retry happens on reopen */ });
        });
    });

    document.addEventListener('click', function (event) {
        if (!mount.contains(event.target)) { close(); }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') { close(); }
    });

    load();
})();
