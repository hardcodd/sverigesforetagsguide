const getNextFieldPanel = (id) => {
	if (!id) return null;

	const normalizedId = id.startsWith("#") ? id.substring(1) : id;

	return document.getElementById(normalizedId)?.closest("li") ?? null;
};

const parseCSVFile = (file) => {
	if (!file) {
		return Promise.resolve({ fields: [], rows: [], delimiter: ",", linebreak: "\r\n" });
	}

	return new Promise((resolve, reject) => {
		Papa.parse(file, {
			header: true,
			skipEmptyLines: "greedy",

			transformHeader: (header) => {
				return header.replace(/^\uFEFF/, "").trim();
			},

			complete: (results) => {
				if (results.errors.length > 0) {
					console.warn("CSV parsing warnings:", results.errors);
				}

				const fields = [...new Set((results.meta.fields ?? []).filter(Boolean))];

				resolve({
					fields,
					rows: results.data,
					delimiter: results.meta.delimiter || ",",
					linebreak: results.meta.linebreak || "\r\n",
				});
			},

			error: reject,
		});
	});
};

const getCSVFields = async (csvFieldInput) => {
	const { fields } = await parseCSVFile(csvFieldInput.files?.[0]);

	return fields;
};

const getModelFields = (pageType) => {
	const selectedOption = pageType.selectedOptions[0];

	const fieldsJSON = selectedOption?.dataset.fields;

	if (!fieldsJSON) {
		return [];
	}

	try {
		return JSON.parse(fieldsJSON);
	} catch (error) {
		console.error("Could not parse model fields:", error, fieldsJSON);

		return [];
	}
};

const createOption = (value, label = value) => {
	const option = document.createElement("option");

	option.value = value;
	option.textContent = label;

	return option;
};

const normalizeFieldName = (value) => {
	return value
		.trim()
		.toLowerCase()
		.replace(/[\s-]+/g, "_");
};

const findMatchingCSVField = (modelFieldName, csvFields, usedCSVFields) => {
	const normalizedModelField = normalizeFieldName(modelFieldName);

	return (
		csvFields.find((csvField) => {
			if (usedCSVFields.has(csvField)) {
				return false;
			}

			return normalizeFieldName(csvField) === normalizedModelField;
		}) ?? ""
	);
};

const updateCSVFieldOptions = (fieldsMappingTable) => {
	const selects = [...fieldsMappingTable.querySelectorAll("select.csv-field")];

	for (const select of selects) {
		const selectedByOtherRows = new Set(
			selects
				.filter((otherSelect) => otherSelect !== select)
				.map((otherSelect) => otherSelect.value)
				.filter(Boolean),
		);

		for (const option of select.options) {
			if (!option.value) {
				option.hidden = false;
				option.disabled = false;
				continue;
			}

			const unavailable = selectedByOtherRows.has(option.value);

			option.hidden = unavailable;
			option.disabled = unavailable;
		}
	}
};

const setMappingFields = (modelFields, csvFields, fieldsMappingTable) => {
	const tbody = fieldsMappingTable.querySelector("tbody");

	if (!tbody) {
		console.error("Fields mapping table body was not found.");
		return;
	}

	tbody.replaceChildren();

	const fragment = document.createDocumentFragment();

	const usedCSVFields = new Set();

	for (const [modelFieldName, modelFieldLabel] of modelFields) {
		const row = document.createElement("tr");

		const uniqCell = document.createElement("td");

		const uniqCheckbox = document.createElement("input");

		uniqCheckbox.type = "checkbox";
		uniqCheckbox.name = `unique[${modelFieldName}]`;

		switch (modelFieldName) {
			case "id":
				uniqCheckbox.checked = true;
				uniqCheckbox.disabled = true;
				break;
			case "slug":
				uniqCheckbox.checked = true;
				uniqCheckbox.disabled = true;
				break;
			case "legal_name":
				uniqCheckbox.checked = true;
				break;
			default:
				break;
		}

		uniqCell.appendChild(uniqCheckbox);

		const modelCell = document.createElement("td");

		const fieldLabel = document.createElement("span");
		const fieldName = document.createElement("span");

		modelCell.classList.add("title");
		fieldLabel.classList.add("import-field-label");
		fieldName.classList.add("import-field-name");

		fieldLabel.textContent = modelFieldLabel;
		fieldName.textContent = modelFieldName;
		modelCell.appendChild(fieldLabel);
		modelCell.appendChild(fieldName);

		const csvCell = document.createElement("td");

		const select = document.createElement("select");

		select.classList.add("csv-field");
		select.dataset.modelField = modelFieldName;

		select.name = `field_mapping[${modelFieldName}]`;

		select.appendChild(createOption("", "---"));

		for (const csvField of csvFields) {
			select.appendChild(createOption(csvField));
		}

		const matchingCSVField = findMatchingCSVField(modelFieldName, csvFields, usedCSVFields);

		if (matchingCSVField) {
			select.value = matchingCSVField;
			usedCSVFields.add(matchingCSVField);
		}

		select.addEventListener("change", () => {
			updateCSVFieldOptions(fieldsMappingTable);
		});

		csvCell.appendChild(select);

		row.appendChild(uniqCell);
		row.appendChild(modelCell);
		row.appendChild(csvCell);

		fragment.appendChild(row);
	}

	tbody.appendChild(fragment);

	updateCSVFieldOptions(fieldsMappingTable);
};

const setProgress = (progress, progressBar, completed, total) => {
	const percent = total === 0 ? 100 : (completed / total) * 100;

	if (progress) {
		progress.hidden = false;
		progress.style.opacity = 1;
	}

	if (progressBar) {
		progressBar.style.width = `${percent}%`;
		progressBar.textContent = `${Math.round(percent)}%`;
	}
};

const readImportResponse = async (response) => {
	const contentType = response.headers.get("content-type") ?? "";

	if (!contentType.toLowerCase().includes("application/json")) {
		return {
			success: false,
			message: `Import endpoint returned HTTP ${response.status} instead of JSON`,
			fatal: true,
		};
	}

	let payload;

	try {
		payload = await response.json();
	} catch (error) {
		console.error("Could not parse import response:", error);

		return {
			success: false,
			message: `Server returned an invalid response (HTTP ${response.status})`,
			fatal: true,
		};
	}

	return {
		success: payload?.success === true,
		message:
			typeof payload?.message === "string"
				? payload.message
				: `Server returned an invalid response (HTTP ${response.status})`,
		fatal: response.status === 404 || response.status === 405,
	};
};

const getImportUrl = (form, submitter) => {
	return (
		form.dataset.importUrl ||
		submitter?.getAttribute("formaction") ||
		form.getAttribute("action") ||
		window.location.href
	);
};

const downloadImportResults = (originalFile, fields, rows, results, delimiter, newline) => {
	const sourceFields = fields.filter((field) => field !== "success" && field !== "message");
	const outputFields = ["success", "message", ...sourceFields];

	const outputData = rows.map((row, index) => [
		results[index]?.success === true,
		results[index]?.message ?? "",
		...sourceFields.map((field) => row[field] ?? ""),
	]);

	// BOM makes UTF-8 text open correctly in Excel as well.
	const csv = `\uFEFF${Papa.unparse({ fields: outputFields, data: outputData }, { delimiter, newline })}`;
	const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	const baseName = originalFile.name.replace(/\.csv$/i, "");

	link.href = url;
	link.download = `${baseName}-import-results.csv`;
	link.hidden = true;

	document.body.appendChild(link);
	link.click();
	link.remove();

	window.setTimeout(() => URL.revokeObjectURL(url), 1000);
};

document.addEventListener("DOMContentLoaded", () => {
	const form = document.getElementById("madloba-import-form");
	const progress = document.querySelector("#import-progress");
	const progressBar = progress?.querySelector(".bar") ?? document.querySelector(".bar");

	if (!form) return;

	const csvFieldInput = form.querySelector("#id_file");

	const pageType = form.querySelector("#id_page-type");

	const fieldsMappingTable = form.querySelector("#id_fields-mapping");

	if (!csvFieldInput || !pageType || !fieldsMappingTable) {
		console.error("Import form fields were not found.");
		return;
	}

	const pageTypePanel = getNextFieldPanel(csvFieldInput.dataset.next);

	const fieldsMappingPanel = getNextFieldPanel(pageType.dataset.next);

	if (!pageTypePanel || !fieldsMappingPanel) {
		console.error("Import form panels were not found.");
		return;
	}

	let isImporting = false;

	const clearMappingFields = () => {
		setMappingFields([], [], fieldsMappingTable);
	};

	const updateMappingFields = async () => {
		const hasFile = csvFieldInput.files.length > 0;

		const hasPageType = Boolean(pageType.value);

		if (!hasFile || !hasPageType) {
			clearMappingFields();
			return;
		}

		const modelFields = getModelFields(pageType);

		try {
			const csvFields = await getCSVFields(csvFieldInput);

			setMappingFields(modelFields, csvFields, fieldsMappingTable);
		} catch (error) {
			console.error("Could not parse CSV file:", error);

			setMappingFields(modelFields, [], fieldsMappingTable);
		}
	};

	const updatePanelVisibility = () => {
		const hasFile = csvFieldInput.files.length > 0;

		const hasPageType = Boolean(pageType.value);

		pageTypePanel.hidden = !hasFile;

		fieldsMappingPanel.hidden = !hasFile || !hasPageType;
	};

	updatePanelVisibility();

	csvFieldInput.addEventListener("change", async () => {
		if (csvFieldInput.files.length === 0) {
			pageType.value = "";
			clearMappingFields();
		}

		updatePanelVisibility();

		if (csvFieldInput.files.length > 0 && pageType.value) {
			await updateMappingFields();
		}
	});

	pageType.addEventListener("change", async () => {
		updatePanelVisibility();

		if (!pageType.value) {
			clearMappingFields();
			return;
		}

		await updateMappingFields();
	});

	form.addEventListener("submit", async (event) => {
		event.preventDefault();

		if (isImporting) return;

		const originalFile = csvFieldInput.files?.[0];

		if (!originalFile) return;

		const importUrl = getImportUrl(form, event.submitter);

		isImporting = true;

		// Capture form values before disabling controls: disabled fields are omitted
		// from FormData by the browser.
		const baseEntries = [...new FormData(form).entries()].filter(([name]) => name !== csvFieldInput.name);

		const controls = [...form.querySelectorAll("input, select, textarea, button")];
		const disabledStates = controls.map((control) => ({
			control,
			disabled: control.disabled,
		}));

		for (const { control } of disabledStates) {
			control.disabled = true;
		}

		form.setAttribute("aria-busy", "true");
		setProgress(progress, progressBar, 0, 1);

		try {
			const { fields, rows, delimiter, linebreak } = await parseCSVFile(originalFile);
			const results = [];

			setProgress(progress, progressBar, 0, rows.length);

			for (const [index, row] of rows.entries()) {
				const requestData = new FormData();

				for (const [name, value] of baseEntries) {
					requestData.append(name, value);
				}

				requestData.append("csv_row", JSON.stringify(row));

				let rowResult;

				try {
					const response = await fetch(importUrl, {
						method: (form.method || "POST").toUpperCase(),
						body: requestData,
						credentials: "same-origin",
						headers: {
							Accept: "application/json",
							"X-Requested-With": "XMLHttpRequest",
						},
					});

					rowResult = await readImportResponse(response);
				} catch (error) {
					console.error(`Could not import CSV row ${index + 1}:`, error);

					rowResult = {
						success: false,
						message: error instanceof Error ? error.message : "Network error",
						fatal: true,
					};
				}

				results.push(rowResult);
				setProgress(progress, progressBar, index + 1, rows.length);

				// A normal application error is JSON with success=false and should not
				// stop the import. Routing, CSRF, proxy, and network errors should.
				if (rowResult.fatal) {
					const skippedMessage = `Not sent: import stopped after row ${index + 1}`;

					for (let skipped = index + 1; skipped < rows.length; skipped += 1) {
						results.push({ success: false, message: skippedMessage });
					}

					break;
				}
			}

			downloadImportResults(originalFile, fields, rows, results, delimiter, linebreak);
		} catch (error) {
			console.error("Could not run CSV import:", error);
		} finally {
			for (const { control, disabled } of disabledStates) {
				control.disabled = disabled;
			}

			form.removeAttribute("aria-busy");
			isImporting = false;
		}
	});
});
