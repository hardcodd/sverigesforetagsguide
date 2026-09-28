import OrganizationFilterSelect from "./organization-filter-select";

/** @type {OrganizationFilterSelect[]} */
const selects = [];
const filterPanel = document.querySelector(".organization-filters__body");

if (filterPanel instanceof HTMLDetailsElement) {
	const mobileViewport = window.matchMedia("(max-width: 767.8px)");
	/**
	 * Keep results visible on mobile, with native form controls usable without JS.
	 * @returns {void}
	 */
	const syncFilterPanel = () => {
		selects.forEach((control) => control.close());
		filterPanel.open = !mobileViewport.matches || filterPanel.dataset.hasErrors === "true";
	};
	syncFilterPanel();
	mobileViewport.addEventListener("change", syncFilterPanel);
}

document.querySelectorAll(".organization-filters select").forEach((select) => {
	if (select instanceof HTMLSelectElement) {
		selects.push(new OrganizationFilterSelect(select, () => selects.forEach((control) => control.close())));
	}
});

const serviceGroups = Array.from(document.querySelectorAll(".organization-filters__group")).filter(
	(group) => group instanceof HTMLDetailsElement,
);

/** Preserve every selection while limiting the accordion to one open group. @param {HTMLDetailsElement} active @returns {void} */
const closeOtherGroups = (active) => {
	serviceGroups.forEach((group) => {
		if (group !== active) group.open = false;
	});
};

const initiallyOpen = serviceGroups.find((group) => group.querySelector('input[type="checkbox"]:checked'));
if (initiallyOpen) {
	closeOtherGroups(initiallyOpen);
	initiallyOpen.open = true;
}
serviceGroups.forEach((group) => {
	group.addEventListener("toggle", () => {
		if (group.open) closeOtherGroups(group);
	});
	group.addEventListener("change", () => {
		const count = group.querySelectorAll('input[type="checkbox"]:checked').length;
		const badge = group.querySelector("[data-group-count]");
		if (badge instanceof HTMLElement) {
			badge.textContent = String(count);
			badge.hidden = count === 0;
		}
		const totalBadge = document.querySelector("[data-service-count]");
		if (totalBadge instanceof HTMLElement) {
			const total = serviceGroups.reduce(
				(sum, item) => sum + item.querySelectorAll('input[type="checkbox"]:checked').length,
				0,
			);
			totalBadge.textContent = String(total);
			totalBadge.hidden = total === 0;
		}
	});
});

/** @typedef {{count: number, counts: Record<string, number>, valid: boolean}} FilterPreview */

/** @param {unknown} value @returns {value is FilterPreview} */
const isFilterPreview = (value) => {
	if (typeof value !== "object" || value === null) return false;
	return (
		"count" in value &&
		typeof value.count === "number" &&
		Number.isSafeInteger(value.count) &&
		value.count >= 0 &&
		"valid" in value &&
		value.valid === true &&
		"counts" in value &&
		typeof value.counts === "object" &&
		value.counts !== null &&
		Object.values(value.counts).every((count) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0)
	);
};

const filterForm = document.querySelector("form.organization-filters");
if (filterForm instanceof HTMLFormElement && filterForm.dataset.countsUrl) {
	const countsUrl = filterForm.dataset.countsUrl;
	const status = filterForm.querySelector("[data-preview-status]");
	const resultCount = filterForm.querySelector("[data-result-count]");
	const optionCounts = Array.from(filterForm.querySelectorAll("[data-option-count]")).filter(
		(element) => element instanceof HTMLElement,
	);
	/** @type {AbortController | null} */
	let pendingRequest = null;
	let revision = 0;
	let timer = 0;

	/** Preview only; submitted results, URL and applied chips change on submit. @param {number} currentRevision @returns {Promise<void>} */
	const updateCounts = async (currentRevision) => {
		const controller = new AbortController();
		pendingRequest = controller;
		const params = new URLSearchParams();
		new FormData(filterForm).forEach((value, key) => {
			if (typeof value === "string" && value !== "") params.append(key, value);
		});
		try {
			const response = await fetch(`${countsUrl}?${params}`, {
				signal: controller.signal,
				headers: { Accept: "application/json" },
				cache: "no-store",
			});
			if (!response.ok) throw new Error("Filter preview failed");
			/** @type {unknown} */
			const preview = await response.json();
			if (
				!isFilterPreview(preview) ||
				optionCounts.some((element) => !((element.dataset.optionCount || "") in preview.counts))
			) {
				throw new Error("Invalid filter preview");
			}
			if (currentRevision !== revision) return;
			optionCounts.forEach((element) => {
				const count = preview.counts[element.dataset.optionCount || ""];
				element.textContent = String(count);
				element.closest(".organization-filters__option")?.classList.toggle("is-empty", count === 0);
			});
			if (resultCount) resultCount.textContent = ` (${preview.count})`;
			if (status instanceof HTMLElement) status.textContent = `${status.dataset.ready} ${preview.count}`;
		} catch {
			if (currentRevision !== revision || controller.signal.aborted) return;
			optionCounts.forEach((element) => {
				element.textContent = "—";
			});
			if (resultCount) resultCount.textContent = "";
			if (status instanceof HTMLElement) status.textContent = status.dataset.failed || "";
		} finally {
			if (currentRevision === revision) filterForm.removeAttribute("aria-busy");
		}
	};

	/** Invalidate stale responses immediately, including during the debounce window. @returns {void} */
	const scheduleCounts = () => {
		const currentRevision = ++revision;
		pendingRequest?.abort();
		window.clearTimeout(timer);
		const selectedMode = filterForm.querySelector('input[name="service_match"]:checked');
		filterForm.querySelectorAll("[data-match-help]").forEach((help) => {
			if (help instanceof HTMLElement) {
				help.hidden =
					help.dataset.matchHelp !== (selectedMode instanceof HTMLInputElement ? selectedMode.value : "all");
			}
		});
		filterForm.setAttribute("aria-busy", "true");
		optionCounts.forEach((element) => {
			element.textContent = "…";
			element.closest(".organization-filters__option")?.classList.remove("is-empty");
		});
		if (resultCount) resultCount.textContent = " (…)";
		if (status instanceof HTMLElement) status.textContent = status.dataset.loading || "";
		timer = window.setTimeout(() => {
			void updateCounts(currentRevision);
		}, 250);
	};
	filterForm.addEventListener("change", scheduleCounts);
	filterForm.addEventListener("input", (event) => {
		if (event.target instanceof HTMLInputElement && event.target.name === "q") scheduleCounts();
	});
}
