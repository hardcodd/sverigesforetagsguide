// @ts-check

/**
 * @typedef {Object} NearbyResponse
 * @property {string} html Server-rendered, escaped organization cards.
 * @property {string | null} next_url Signed continuation URL, or null at the end.
 */

/** @param {unknown} value @returns {value is NearbyResponse} */
function isNearbyResponse(value) {
	return (
		typeof value === "object" &&
		value !== null &&
		"html" in value &&
		typeof value.html === "string" &&
		"next_url" in value &&
		(value.next_url === null || typeof value.next_url === "string")
	);
}

/** Attach a single-flight loader and keep failures retryable. @returns {void} */
function initializeNearbyOrganizations() {
	const button = document.querySelector(".nearby-organizations__load-more");
	const items = document.querySelector("#nearby-organization-items");
	const status = document.querySelector(".nearby-organizations__status");
	if (
		!(button instanceof HTMLButtonElement) ||
		!(items instanceof HTMLUListElement) ||
		!(status instanceof HTMLParagraphElement)
	)
		return;

	const label = button.textContent;
	button.hidden = false;
	button.addEventListener("click", async () => {
		const url = button.dataset.nextUrl;
		if (button.disabled || !url) return;

		button.disabled = true;
		button.textContent = button.dataset.loadingText ?? label;
		items.setAttribute("aria-busy", "true");
		status.textContent = "";
		const controller = new AbortController();
		const timeout = window.setTimeout(() => controller.abort(), 15000);
		try {
			const response = await fetch(url, {
				headers: { Accept: "application/json" },
				credentials: "same-origin",
				signal: controller.signal,
			});
			if (!response.ok) throw new Error("Nearby request failed");
			/** @type {unknown} */
			const data = await response.json();
			if (!isNearbyResponse(data)) throw new Error("Invalid nearby response");

			const template = document.createElement("template");
			template.innerHTML = data.html;
			// Editors can change ranking between clicks; do not repeat visible cards.
			const visibleLinks = new Set(Array.from(items.querySelectorAll("a[href]"), (link) => link.getAttribute("href")));
			for (const item of Array.from(template.content.children)) {
				const href = item.querySelector("a[href]")?.getAttribute("href");
				if (href && visibleLinks.has(href)) item.remove();
				else if (href) visibleLinks.add(href);
			}
			const firstLink = template.content.querySelector("a");
			items.append(template.content);
			button.dataset.nextUrl = data.next_url ?? "";
			button.hidden = data.next_url === null;
			status.textContent = (data.next_url ? button.dataset.successText : button.dataset.completeText) ?? "";
			if (firstLink instanceof HTMLAnchorElement) firstLink.focus({ preventScroll: true });
		} catch {
			status.textContent = button.dataset.errorText ?? "";
		} finally {
			window.clearTimeout(timeout);
			items.removeAttribute("aria-busy");
			button.disabled = false;
			button.textContent = label;
		}
	});
}

initializeNearbyOrganizations();
