document.addEventListener("DOMContentLoaded", () => {
	const form = document.querySelector("#import-reviews-form");
	if (!form) return;
	const gettext = window.gettext || ((message) => message);

	const csvImport = window.MadlobaAdminCsvImport;
	if (!csvImport) {
		console.error(gettext("CSV import utilities are unavailable."));
		return;
	}

	const csrf = form.querySelector("input[name='csrfmiddlewaretoken']");
	const progress = document.querySelector("#import-progress");
	const progressBar = progress?.querySelector(".bar");
	const requiredFields = ["id", "user", "rate", "date", "text"];
	const batchSize = 10;

	if (!csrf || !progressBar) {
		console.error(gettext("Review import form controls are unavailable."));
		return;
	}
	if (!window.Papa) {
		console.error(gettext("CSV parser is unavailable."));
		return;
	}

	const setProgress = (processed, total) => {
		const percentage = total ? Math.round((processed / total) * 100) : 100;
		progress.classList.add("active");
		progressBar.style.width = `${percentage}%`;
		progressBar.textContent = `${percentage}%`;
	};

	const postBatch = async (rows) => {
		const response = await fetch(form.action, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				"X-CSRFToken": csrf.value,
			},
			body: JSON.stringify(rows),
		});

		let data;
		try {
			data = await response.json();
		} catch (_) {
			const error = new Error(`HTTP ${response.status}`);
			error.status = response.status;
			throw error;
		}

		if (!response.ok || !data.success || !Array.isArray(data.results)) {
			const error = new Error(data.message || `HTTP ${response.status}`);
			error.status = response.status;
			throw error;
		}
		if (data.results.length !== rows.length) {
			throw new Error(gettext("The server returned an incomplete import result."));
		}
		return data.results;
	};

	const requestFailedResult = (error) => ({
		success: false,
		code: "request_failed",
		message: error.message || gettext("Import request failed."),
	});

	const postBatchWithFallback = async (rows) => {
		try {
			return await postBatch(rows);
		} catch (batchError) {
			if (batchError.status && batchError.status < 500) {
				return rows.map(() => requestFailedResult(batchError));
			}

			const results = [];
			for (const row of rows) {
				try {
					const [result] = await postBatch([row]);
					results.push(result);
				} catch (rowError) {
					results.push(requestFailedResult(rowError));
				}
			}
			return results;
		}
	};

	const importRows = async (rows) => {
		let processed = 0;
		let successful = 0;
		let warnings = 0;
		let errors = 0;
		const importResults = [];
		setProgress(0, rows.length);

		for (let offset = 0; offset < rows.length; offset += batchSize) {
			const batch = rows.slice(offset, offset + batchSize);
			const results = await postBatchWithFallback(batch);

			results.forEach((result) => {
				importResults.push(result);
				if (result.success) successful += 1;
				else if (result.code === "already_exists") warnings += 1;
				else errors += 1;
			});
			processed += batch.length;
			setProgress(processed, rows.length);
		}

		alert(
			`${gettext("Import completed")}: ${processed}/${rows.length}. ` +
				`${gettext("Successful")}: ${successful}. ` +
				`${gettext("Warnings")}: ${warnings}. ` +
				`${gettext("Errors")}: ${errors}.`,
		);
		return importResults;
	};

	form.addEventListener("submit", (event) => {
		event.preventDefault();

		const file = form.file?.files?.[0];
		if (!file) return;

		window.Papa.parse(file, {
			header: true,
			skipEmptyLines: "greedy",
			transformHeader: (header) => header.replace(/^\uFEFF/, "").trim(),
			encoding: "utf-8",
			complete: async (result) => {
				const fields = result.meta?.fields || [];
				const missingFields = requiredFields.filter((field) => !fields.includes(field));
				if (missingFields.length) {
					alert(`${gettext("Missing required CSV fields")}: ${missingFields.join(", ")}`);
					return;
				}

				const sourceRows = result.data || [];
				const rows = sourceRows.map((row) => ({
					id: row.id,
					user: row.user,
					rate: row.rate,
					date: row.date,
					text: row.text,
				}));

				const controls = form.querySelectorAll("input, button");
				controls.forEach((control) => {
					control.disabled = true;
				});
				try {
					const importResults = await importRows(rows);
					csvImport.downloadImportResults(
						file,
						fields,
						sourceRows,
						importResults,
						result.meta?.delimiter,
						result.meta?.linebreak,
					);
				} finally {
					controls.forEach((control) => {
						control.disabled = false;
					});
				}
			},
			error: (error) => alert(`${gettext("Parsing error")}: ${error.message}`),
		});
	});
});
