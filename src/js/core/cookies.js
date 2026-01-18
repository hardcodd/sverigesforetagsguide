// cookie.js — universal ESM module with no external deps.
// Works in browsers with real document.cookie and in SSR via an in-memory fallback.

/**
 * @typedef {Object} CookieSetOptions
 * @property {string} [path="/"]        - Cookie path
 * @property {string} [domain]          - Cookie domain (omit unless required)
 * @property {"Strict"|"Lax"|"None"} [sameSite="Lax"] - SameSite policy
 * @property {boolean} [secure]         - Defaults to true on HTTPS; forced true when SameSite=None
 * @property {number|Date} [expires]    - Expiration as Date or number of days
 * @property {number} [maxAge]          - Max-Age in seconds
 * @property {(v:string)=>string} [encode] - Custom value encoder
 */

class MemoryCookieStore {
	constructor() {
		this.map = new Map();
	}
	get cookie() {
		// Serialize the map to a cookie-like string: "a=b; c=d"
		return [...this.map.entries()].map(([k, v]) => `${k}=${v}`).join("; ");
	}
	set cookie(str) {
		// Emulate document.cookie "write-only" semantics: accept a single "name=value; ..." assignment
		const pair = String(str).split(";")[0];
		const idx = pair.indexOf("=");
		if (idx > -1) {
			const name = pair.slice(0, idx).trim();
			const value = pair.slice(idx + 1).trim();
			this.map.set(name, value);
		}
	}
}

const hasDocument = typeof document !== "undefined" && typeof document.cookie === "string";
const cookieTarget = hasDocument ? document : new MemoryCookieStore();

// Safe encode/decode helpers (handle + as space on decode)
const defaultEncode = (v) => encodeURIComponent(v);
const defaultDecode = (v) => {
	try {
		return decodeURIComponent(String(v).replace(/\+/g, " "));
	} catch {
		return v;
	}
};

function toExpires(expires) {
	if (expires == null) return "";
	if (expires instanceof Date) return `; Expires=${expires.toUTCString()}`;
	if (typeof expires === "number") {
		const d = new Date();
		d.setTime(d.getTime() + expires * 24 * 60 * 60 * 1000);
		return `; Expires=${d.toUTCString()}`;
	}
	return "";
}

function toMaxAge(maxAge) {
	if (typeof maxAge === "number" && Number.isFinite(maxAge)) {
		return `; Max-Age=${Math.trunc(maxAge)}`;
	}
	return "";
}

function normalizeSameSite(v) {
	return v === "Strict" || v === "None" ? v : "Lax";
}

function serializeCookie(name, value, opts = {}) {
	const encode = opts.encode || defaultEncode;

	if (!name || /[\s;=]/.test(name)) {
		throw new Error("Invalid cookie name.");
	}

	// Non-string values are serialized as JSON with "j:" prefix
	let raw = value;
	if (typeof value !== "string") raw = "j:" + JSON.stringify(value);
	const val = encode(String(raw));

	const path = opts.path ?? "/";
	const domain = opts.domain; // universal: do not auto-infer domains
	const sameSite = normalizeSameSite(opts.sameSite);
	let secure =
		typeof opts.secure === "boolean"
			? opts.secure
			: typeof window !== "undefined" && window.location && window.location.protocol === "https:";

	// Browsers require Secure when SameSite=None
	if (sameSite === "None") secure = true;

	let str = `${name}=${val}`;
	str += path ? `; Path=${path}` : "";
	str += domain ? `; Domain=${domain}` : "";
	str += toExpires(opts.expires);
	str += toMaxAge(opts.maxAge);
	str += secure ? `; Secure` : "";
	str += `; SameSite=${sameSite}`;

	return str;
}

function parseCookieString(cookieStr, decode = defaultDecode) {
	const out = {};
	if (!cookieStr) return out;

	// document.cookie string looks like "a=b; c=d; e=f"
	const parts = String(cookieStr).split(/;\s*/);
	for (const part of parts) {
		const eqIdx = part.indexOf("=");
		if (eqIdx < 0) continue;
		const name = part.slice(0, eqIdx).trim();
		const value = part.slice(eqIdx + 1).trim();

		let decoded = decode(value);
		if (decoded.startsWith("j:")) {
			try {
				decoded = JSON.parse(decoded.slice(2));
			} catch {}
		}
		out[name] = decoded;
	}
	return out;
}

function parseAll(decode = defaultDecode) {
	const cookieStr = cookieTarget.cookie || "";
	return parseCookieString(cookieStr, decode);
}

const CookieAPI = {
	/**
	 * Set a cookie. Passing null/undefined deletes the cookie.
	 */
	set(name, value, options = {}) {
		if (value === null || value === undefined) {
			return this.delete(name, options);
		}
		cookieTarget.cookie = serializeCookie(name, value, options);
	},

	/**
	 * Get a cookie by name. If stored as JSON ("j:" prefix), returns the parsed object.
	 * Use { raw: true } to return the serialized string form.
	 */
	get(name, opts = {}) {
		const all = parseAll(opts.decode || defaultDecode);
		const v = Object.prototype.hasOwnProperty.call(all, name) ? all[name] : null;
		if (v == null) return null;
		if (opts.raw === true && typeof v !== "string") {
			return "j:" + JSON.stringify(v);
		}
		return v;
	},

	/** Check if a cookie exists. */
	has(name) {
		const all = parseAll();
		return Object.prototype.hasOwnProperty.call(all, name);
	},

	/**
	 * Delete a cookie by setting an expired date and Max-Age=0.
	 * Important: use the same path/domain as when it was set.
	 */
	delete(name, options = {}) {
		const path = options.path ?? "/";
		const domain = options.domain;
		const sameSite = normalizeSameSite(options.sameSite);
		const secure =
			typeof options.secure === "boolean"
				? options.secure
				: typeof window !== "undefined" && window.location && window.location.protocol === "https:";

		cookieTarget.cookie =
			`${name}=; Path=${path}` +
			(domain ? `; Domain=${domain}` : "") +
			`; Expires=Thu, 01 Jan 1970 00:00:00 GMT` +
			`; Max-Age=0` +
			(secure ? `; Secure` : "") +
			`; SameSite=${sameSite}`;
	},

	/** Get all cookies as an object (JSON values are parsed). */
	getAll() {
		return parseAll();
	},

	/** Get all cookie keys. */
	keys() {
		return Object.keys(parseAll());
	},

	/** Sugar: set JSON explicitly. */
	setJSON(name, obj, options = {}) {
		this.set(name, obj, options);
	},

	/** Sugar: get as JSON object (or null if not an object). */
	getJSON(name) {
		const v = this.get(name);
		return v && typeof v === "object" ? v : null;
	},
};

/** Compatibility object + default export */
export const cookie = {
	set: CookieAPI.set.bind(CookieAPI),
	get: CookieAPI.get.bind(CookieAPI),
	delete: CookieAPI.delete.bind(CookieAPI),
	getAll: CookieAPI.getAll.bind(CookieAPI),
	has: CookieAPI.has.bind(CookieAPI),
	keys: CookieAPI.keys.bind(CookieAPI),
	setJSON: CookieAPI.setJSON.bind(CookieAPI),
	getJSON: CookieAPI.getJSON.bind(CookieAPI),
};

export default cookie;

/**
 * Extra utilities for server/SSR usage:
 *  - serialize(): build a Set-Cookie header value
 *  - parse(): parse the Cookie request header string
 */
export function serialize(name, value, options) {
	return serializeCookie(name, value, options);
}

export function parse(cookieHeaderString, decode = defaultDecode) {
	return parseCookieString(cookieHeaderString, decode);
}
