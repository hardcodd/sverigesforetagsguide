// ======= UTILITIES ==================================================
const escapeHtml = (val) => {
	if (val === null || val === undefined) return "";
	const s = String(val);
	return s;
	// .replace(/&/g, "&amp;")
	// .replace(/</g, "&lt;")
	// .replace(/>/g, "&gt;")
	// .replace(/"/g, "&quot;")
	// .replace(/'/g, "&#039;");
};

const truncate = (val, max = 50) => {
	const s = String(val ?? "");
	return s.length > max ? `${s.slice(0, max)}…` : s;
};

const updateProgressBar = (barEl, percentage) => {
	const p = Math.max(0, Math.min(100, percentage | 0));
	barEl.style.width = `${p}%`;
	barEl.textContent = `${p}%`;
};

// ======= TABLE RENDERING ============================================
const renderTable = (data, progress, progressBar) => {
	return new Promise((resolve) => {
		const table = document.querySelector(".csv-table");
		if (!table) return resolve([]);

		table.innerHTML = "";

		// show progress
		progress?.classList?.add("active");
		updateProgressBar(progressBar, 0);

		if (!Array.isArray(data) || data.length === 0) {
			const empty = document.createElement("caption");
			empty.textContent = "No data to import";
			table.appendChild(empty);
			return resolve([]);
		}

		// thead
		const thead = document.createElement("thead");
		const headerRow = document.createElement("tr");
		const headers = Object.keys(data[0] ?? {});
		headers.forEach((key) => {
			const th = document.createElement("th");
			th.textContent = key;
			headerRow.appendChild(th);
		});
		const statusTh = document.createElement("th");
		statusTh.textContent = "Status";
		headerRow.insertBefore(statusTh, headerRow.firstChild);
		thead.appendChild(headerRow);
		table.appendChild(thead);

		// tbody
		const tbody = document.createElement("tbody");
		let index = 0;

		for (const row of data) {
			index += 1;
			const tr = document.createElement("tr");
			tr.id = `row-${index}`;

			headers.forEach((key) => {
				const raw = row[key];
				const td = document.createElement("td");
				const display = escapeHtml(truncate(raw, 50));
				td.textContent = display;
				tr.appendChild(td);
			});

			const statusTd = document.createElement("td");
			statusTd.classList.add("status-message");
			tr.insertBefore(statusTd, tr.firstChild);

			tbody.appendChild(tr);
		}

		table.appendChild(tbody);
		resolve(data);
	});
};

// ======= SEQUENTIAL SENDING =========================================
const postRow = async (url, csrfToken, rowObj) => {
	const res = await fetch(url, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-CSRFToken": csrfToken,
		},
		body: JSON.stringify(rowObj),
	});

	// Server may return non-JSON on HTTP 500, handle gracefully
	let json = {};
	try {
		json = await res.json();
	} catch (_) {}

	// Normalize contract: consider success if 2xx + {success:true}
	const ok = res.ok && json && json.success === true;
	const message = json?.message || (res.ok ? "OK" : `HTTP ${res.status}`);
	return { ok, message };
};

const importSequentially = async (url, data, csrf, progressBar) => {
	const total = data.length;
	let processed = 0;
	const tbody = document.querySelector(".csv-table tbody");

	for (let i = 0; i < total; i += 1) {
		const row = data[i];
		row.is_first = i === 0;
		row.is_last = i === total - 1;
		const rowId = `row-${i + 1}`;
		const tr = document.getElementById(rowId);
		const statusTd = tr?.querySelector(".status-message");

		try {
			const form = document.querySelector("#import-organizations-form");
			const result = await postRow(url, csrf.value, row);

			if (result.ok) {
				tr?.classList?.remove("error");
				tr?.classList?.add("success");
				tr.querySelector(".status-message").textContent = "Imported!";
			} else {
				tr?.classList?.remove("success");
				tr?.classList?.add(result.message === "Already exists!" ? "warning" : "error");
				statusTd.textContent = result.message;
			}
		} catch (err) {
			tr?.classList?.remove("success");
			tr?.classList?.add("error");
			statusTd.textContent = err?.message || err;
		} finally {
			processed += 1;
			const pct = Math.round((processed / total) * 100);
			updateProgressBar(progressBar, pct);
			// Small delay (optional) to avoid overloading the server:
			// await new Promise(r => setTimeout(r, 20));
		}
	}

	// Reorder rows: success first, then warnings, then errors
	const successRowsLength = tbody.querySelectorAll("tr.success").length;
	const warningRows = tbody.querySelectorAll("tr.warning");
	const errorRows = tbody.querySelectorAll("tr.error");

	warningRows.forEach((r) => tbody.appendChild(r));
	errorRows.forEach((r) => tbody.appendChild(r));

	alert(
		`Import completed: ${processed} of ${total} rows processed. Successful: ${successRowsLength}, Warnings: ${warningRows.length}, Errors: ${errorRows.length}.`,
	);
};

// ======= INITIALIZATION =============================================
document.addEventListener("DOMContentLoaded", () => {
	const form = document.querySelector("#import-organizations-form");
	if (!form) return;

	const csrf = form.querySelector("input[name='csrfmiddlewaretoken']");
	const progress = document.querySelector("#import-progress");
	const progressBar = document.querySelector(".bar");

	form.addEventListener("submit", (e) => {
		e.preventDefault();

		const file = form.file?.files?.[0];
		if (!file) return;

		Papa.parse(file, {
			header: true,
			skipEmptyLines: true,
			encoding: "utf-8",
			complete: async (result) => {
				const rows = result?.data?.filter(Boolean) || [];
				await renderTable(rows, progress, progressBar);
				// IMPORTANT: send sequentially
				await importSequentially(form.action, rows, csrf, progressBar);
			},
			error: (err) => alert("Parsing error: " + err.message),
		});
	});
});
