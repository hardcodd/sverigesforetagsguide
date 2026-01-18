// consent.js — ES module, depends only on ./cookie.js (universal cookie helper)
// All comments/strings in English only.

import cookie from "../core/cookies";

const _ = window.gettext && typeof window.gettext === "function" ? window.gettext : (s) => s; // Fallback if django JS i18n is not yet loaded

const CONSENT_COOKIE = "ng_cookie_consent";
const CONSENT_MAX_AGE_DAYS = 365;

const DEFAULT_CONSENT = {
	necessary: true,
	analytics: false,
	marketing: false,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Build cookie.set options (domain is optional; use only if provided via window.NG_COOKIE_DOMAIN) */
function getCookieOptions() {
	const isHttps = typeof location !== "undefined" && location.protocol === "https:";
	const domain =
		typeof window !== "undefined" && typeof window.NG_COOKIE_DOMAIN === "string" && window.NG_COOKIE_DOMAIN.trim()
			? window.NG_COOKIE_DOMAIN.trim()
			: undefined;

	return {
		path: "/",
		sameSite: "Lax",
		secure: isHttps, // secure on HTTPS
		expires: CONSENT_MAX_AGE_DAYS,
		...(domain ? { domain } : {}),
	};
}

/** Backward-compatible read:
 * - supports cookie.js JSON ("j:" prefix) via cookie.getJSON()
 * - supports legacy plain-JSON string stored earlier by older code
 */
function readConsent() {
	const obj = cookie.getJSON(CONSENT_COOKIE);
	if (obj && typeof obj === "object") return obj;

	const raw = cookie.get(CONSENT_COOKIE);
	if (typeof raw === "string" && raw) {
		// Try to parse legacy '{"necessary":...}' string
		try {
			return JSON.parse(raw);
		} catch {}
	}
	return null;
}

function writeConsent(consent) {
	cookie.setJSON(CONSENT_COOKIE, consent, getCookieOptions());
}

function deleteConsent() {
	// Use same path/domain/samesite/secure to ensure deletion
	cookie.delete(CONSENT_COOKIE, getCookieOptions());
}

function applyConsent(consent) {
	// Execute deferred scripts by category
	$$('script[type="text/plain"][data-consent-category]').forEach((script) => {
		const cat = script.getAttribute("data-consent-category");
		if (cat && consent[cat]) {
			const s = document.createElement("script");
			// Copy attributes except type
			for (const { name, value } of Array.from(script.attributes)) {
				if (name === "type") continue;
				s.setAttribute(name, value);
			}
			s.text = script.text;
			s.type = "text/javascript";
			script.replaceWith(s);
		}
	});

	// Optional: update gtag consent if present
	if (typeof window.gtag === "function") {
		try {
			window.gtag("consent", "update", {
				ad_user_data: consent.marketing ? "granted" : "denied",
				ad_personalization: consent.marketing ? "granted" : "denied",
				ad_storage: consent.marketing ? "granted" : "denied",
				analytics_storage: consent.analytics ? "granted" : "denied",
			});
		} catch {
			/* noop */
		}
	}

	// Emit a custom event for app integrations
	document.dispatchEvent(new CustomEvent("ng:consent-changed", { detail: { consent } }));
}

function saveConsent(consent, announceMessage) {
	writeConsent(consent);
	applyConsent(consent);
	announce(announceMessage || _("Cookie preferences saved."));
	hideBanner();
	hideModal();
	const manage = $('[data-cc="open-preferences"]');
	if (manage) manage.hidden = false;
}

function announce(message) {
	const region = $(".cc-sr");
	if (!region) return;
	region.hidden = false;
	region.textContent = message;
	setTimeout(() => {
		region.hidden = true;
		region.textContent = "";
	}, 2000);
}

function showBanner() {
	const banner = $("#cookie-consent");
	if (banner) banner.hidden = false;
}

function hideBanner() {
	const banner = $("#cookie-consent");
	if (banner) banner.hidden = true;
}

function showModal() {
	const modal = $(".cc-modal");
	if (!modal) return;
	modal.hidden = false;
	const dialog = $(".cc-modal__dialog", modal);
	dialog?.focus();
	trapFocus(modal);
}

function hideModal() {
	const modal = $(".cc-modal");
	if (!modal) return;
	releaseFocus(modal);
	modal.hidden = true;
}

let focusTrapHandler = null;
function trapFocus(root) {
	releaseFocus(root);
	focusTrapHandler = (e) => {
		if (e.key !== "Tab") return;
		const focusables = $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', root).filter(
			(el) => !el.hasAttribute("disabled") && !el.getAttribute("aria-hidden"),
		);
		if (!focusables.length) return;
		const first = focusables[0];
		const last = focusables[focusables.length - 1];
		if (e.shiftKey && document.activeElement === first) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && document.activeElement === last) {
			e.preventDefault();
			first.focus();
		}
	};
	root.addEventListener("keydown", focusTrapHandler);
}

function releaseFocus(root) {
	if (focusTrapHandler) {
		root.removeEventListener("keydown", focusTrapHandler);
		focusTrapHandler = null;
	}
}

function getConsent() {
	return readConsent();
}

function hasConsent(category) {
	const c = readConsent();
	return !!(c && c[category]);
}

function initUIFromConsent(consent) {
	$$('input[data-cc-cat="analytics"]').forEach((el) => {
		el.checked = !!consent.analytics;
	});
	$$('input[data-cc-cat="marketing"]').forEach((el) => {
		el.checked = !!consent.marketing;
	});
}

function currentSelections() {
	return {
		...DEFAULT_CONSENT,
		analytics: !!$('input[data-cc-cat="analytics"]')?.checked,
		marketing: !!$('input[data-cc-cat="marketing"]')?.checked,
	};
}

function wireEvents() {
	document.addEventListener("click", (e) => {
		const btn = e.target.closest("[data-cc]");
		if (!btn) return;

		const action = btn.getAttribute("data-cc");
		if (action === "accept") {
			saveConsent({ necessary: true, analytics: true, marketing: true }, _("All cookies accepted."));
		}
		if (action === "reject") {
			saveConsent({ necessary: true, analytics: false, marketing: false }, _("Only necessary cookies allowed."));
		}
		if (action === "preferences") {
			const c = readConsent() || DEFAULT_CONSENT;
			initUIFromConsent(c);
			showModal();
		}
		if (action === "save") {
			const c = currentSelections();
			saveConsent(c, _("Cookie preferences saved."));
		}
		if (action === "close") {
			hideModal();
		}
		if (action === "open-preferences") {
			const c = readConsent() || DEFAULT_CONSENT;
			initUIFromConsent(c);
			showModal();
		}
	});

	document.addEventListener("keydown", (e) => {
		if (e.key === "Escape") hideModal();
	});
}

function firstRender() {
	const existing = readConsent();
	if (existing) {
		// Apply immediately for deferred scripts on subsequent page loads
		applyConsent(existing);
		const manage = $('[data-cc="open-preferences"]');
		if (manage) manage.hidden = false;
		return;
	}
	showBanner();
}

function exposeAPI() {
	window.NGCookieConsent = {
		openPreferences: () => {
			const c = readConsent() || DEFAULT_CONSENT;
			initUIFromConsent(c);
			showModal();
		},
		getConsent,
		hasConsent,
		// Optional: programmatic setter (e.g., server-driven defaults or admin tools)
		setConsent: (consent) => saveConsent({ ...DEFAULT_CONSENT, ...consent }, _("Cookie preferences saved.")),
		// Optional: reset to defaults (for debugging)
		reset: () => {
			deleteConsent();
			showBanner();
		},
	};
}

document.addEventListener("DOMContentLoaded", () => {
	wireEvents();
	exposeAPI();
	firstRender();
});
