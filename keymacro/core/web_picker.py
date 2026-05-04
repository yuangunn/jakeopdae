"""Interactive element picker — Chrome-DevTools-style overlay that lets the
user click a DOM element to harvest a Playwright-friendly selector.

The selector is ranked by stability:

  1. ``role=button[name="학습하기"]`` — explicit/implicit ARIA role + accessible name
  2. ``#stable-id`` — element has a stable id attribute
  3. ``button:has-text("...")`` — tag-scoped text match (only for buttons / links)
  4. ``main > div:nth-of-type(2) > button`` — CSS path (last resort)

The JS overlay runs inside the page; Python polls for completion. ESC
cancels. After a result is harvested or the timeout elapses, the overlay
cleans up after itself (removes the highlight, info banner, and event
listeners) so the page is left untouched.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .web import WebSession

log = logging.getLogger(__name__)


# ``r"""..."""`` so JS backslashes survive as-is. Keep the JS self-contained
# (no external script tags); the IIFE installs ``window.__keymacroPicker``
# with ``cleanup`` so we can dispose remotely.
_PICKER_JS = r"""
(() => {
  if (window.__keymacroPicker && window.__keymacroPicker.active) {
    return; // already picking
  }

  const HL_BORDER = '#E8B26A';   // brass
  const HL_BG = 'rgba(232,178,106,0.16)';
  const PANEL_BG = '#1A1813';
  const PANEL_FG = '#F2EBDA';
  const PANEL_BORDER = '#46423A';

  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed; pointer-events: none;
    z-index: 2147483647;
    border: 2px solid ${HL_BORDER};
    background: ${HL_BG};
    border-radius: 4px;
    transition: all 60ms ease-out;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.04);
  `;

  const info = document.createElement('div');
  info.style.cssText = `
    position: fixed; top: 12px; left: 50%;
    transform: translateX(-50%);
    z-index: 2147483647;
    background: ${PANEL_BG}; color: ${PANEL_FG};
    border: 1px solid ${PANEL_BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    font: 13px 'Pretendard Variable','Apple SD Gothic Neo',sans-serif;
    box-shadow: 0 6px 20px rgba(0,0,0,0.45);
    pointer-events: none;
    max-width: min(80vw, 720px);
  `;
  info.innerHTML =
    `<strong style="color:${HL_BORDER}">keymacro</strong>` +
    ` · 클릭할 요소를 선택하세요` +
    ` <span style="opacity:.7;margin-left:8px">Esc로 취소</span>`;

  document.documentElement.appendChild(overlay);
  document.documentElement.appendChild(info);

  let currentTarget = null;

  const escapeHtml = s => String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));

  function update(target) {
    if (!target || target === overlay || target === info) return;
    currentTarget = target;
    const r = target.getBoundingClientRect();
    overlay.style.left = r.left + 'px';
    overlay.style.top = r.top + 'px';
    overlay.style.width = r.width + 'px';
    overlay.style.height = r.height + 'px';
    const sel = computeSelector(target);
    info.innerHTML =
      `<strong style="color:${HL_BORDER}">keymacro</strong>` +
      ` · <code style="background:#26241D;padding:2px 6px;border-radius:4px">` +
      `${escapeHtml(sel)}</code>`;
  }

  function onMouseMove(e) {
    const el = document.elementFromPoint(e.clientX, e.clientY);
    update(el);
  }

  function onClick(e) {
    if (!currentTarget) return;
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    const sel = computeSelector(currentTarget);
    window.__keymacroPicker.result = sel;
    cleanup();
  }

  function onKeyDown(e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
      e.preventDefault(); e.stopPropagation();
      window.__keymacroPicker.cancelled = true;
      cleanup();
    }
  }

  function cleanup() {
    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
    overlay.remove(); info.remove();
    window.__keymacroPicker.active = false;
  }

  // --- selector ranking ---------------------------------------------------

  function computeSelector(el) {
    const role = (el.getAttribute('role') || '').trim().toLowerCase()
                 || implicitRole(el);
    const name = accessibleName(el);
    if (role && name) {
      return `role=${role}[name=${JSON.stringify(name)}]`;
    }
    if (el.id && /^[A-Za-z][A-Za-z0-9_\-:]*$/.test(el.id)) {
      return '#' + el.id;
    }
    const text = (el.innerText || el.textContent || '').trim().slice(0, 60);
    if (text && (el.tagName === 'BUTTON' || el.tagName === 'A')) {
      return `${el.tagName.toLowerCase()}:has-text(${JSON.stringify(text)})`;
    }
    return cssPath(el);
  }

  function implicitRole(el) {
    const t = el.tagName;
    if (t === 'BUTTON') return 'button';
    if (t === 'A') return el.hasAttribute('href') ? 'link' : '';
    if (t === 'SELECT') return 'combobox';
    if (t === 'TEXTAREA') return 'textbox';
    if (/^H[1-6]$/.test(t)) return 'heading';
    if (t === 'IMG' && el.hasAttribute('alt')) return 'img';
    if (t === 'NAV') return 'navigation';
    if (t === 'MAIN') return 'main';
    if (t === 'ARTICLE') return 'article';
    if (t === 'INPUT') {
      const ity = (el.type || 'text').toLowerCase();
      if (['button','submit','reset'].includes(ity)) return 'button';
      if (ity === 'checkbox') return 'checkbox';
      if (ity === 'radio') return 'radio';
      if (ity === 'range') return 'slider';
      return 'textbox';
    }
    return '';
  }

  function accessibleName(el) {
    const aria = (el.getAttribute('aria-label') || '').trim();
    if (aria) return aria;

    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const txt = labelledby.split(/\s+/)
        .map(id => document.getElementById(id))
        .filter(Boolean)
        .map(e => (e.innerText || e.textContent || '').trim())
        .join(' ').trim();
      if (txt) return txt;
    }

    if (el.tagName === 'INPUT' && el.id) {
      try {
        const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (lbl) return (lbl.innerText || lbl.textContent || '').trim();
      } catch (_) {}
    }

    if (el.tagName === 'IMG' && el.hasAttribute('alt')) {
      return (el.alt || '').trim();
    }

    const title = (el.getAttribute('title') || '').trim();
    if (title) return title;

    // Visible text — prefer innerText (respects display:none) over textContent.
    const t = (el.innerText || el.textContent || '').trim();
    if (t.length > 80) return t.slice(0, 80);
    return t;
  }

  function cssPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
      let part = cur.tagName.toLowerCase();
      if (cur.id && /^[A-Za-z][A-Za-z0-9_\-:]*$/.test(cur.id)) {
        parts.unshift('#' + cur.id);
        break;
      }
      const parent = cur.parentNode;
      if (parent && parent.children) {
        const sibs = Array.from(parent.children).filter(s => s.tagName === cur.tagName);
        if (sibs.length > 1) {
          part += `:nth-of-type(${sibs.indexOf(cur) + 1})`;
        }
      }
      parts.unshift(part);
      cur = parent;
    }
    return parts.join(' > ');
  }

  // --- attach ------------------------------------------------------------

  document.addEventListener('mousemove', onMouseMove, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('keydown', onKeyDown, true);

  window.__keymacroPicker = {
    active: true,
    result: null,
    cancelled: false,
    cleanup,
  };
})();
"""


def pick_element_selector(
    web_session: WebSession,
    *,
    timeout_s: float = 60.0,
    poll_interval_s: float = 0.15,
) -> Optional[str]:
    """Inject the picker overlay and block until the user clicks an
    element (returns the selector) or presses Esc / the timeout elapses
    (returns None)."""
    page = web_session.page()
    page.evaluate(_PICKER_JS)

    deadline = time.monotonic() + timeout_s
    state = {"active": True, "result": None, "cancelled": False}
    try:
        while time.monotonic() < deadline:
            try:
                state = page.evaluate(
                    "() => ({"
                    "  result: (window.__keymacroPicker || {}).result || null,"
                    "  cancelled: !!((window.__keymacroPicker || {}).cancelled),"
                    "  active: !!((window.__keymacroPicker || {}).active)"
                    "})"
                ) or state
            except Exception:
                # Page navigated or context destroyed; give up.
                log.debug("picker poll evaluate raised", exc_info=True)
                return None

            if state.get("cancelled"):
                log.info("element picker cancelled by user")
                return None
            if state.get("result"):
                sel = str(state["result"])
                log.info("element picker returned: %s", sel)
                return sel
            if not state.get("active"):
                # Picker torn down outside our control.
                return None

            time.sleep(poll_interval_s)
    finally:
        # Best-effort cleanup; ignore errors if the page is already gone.
        try:
            page.evaluate(
                "() => { if (window.__keymacroPicker)"
                " window.__keymacroPicker.cleanup && window.__keymacroPicker.cleanup(); }"
            )
        except Exception:
            log.debug("picker cleanup raised", exc_info=True)

    log.info("element picker timed out")
    return None
