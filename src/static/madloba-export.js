(() => {
	const requestJSON = async (url, options = {}) => {
		if (!url) {
			throw new Error(gettext("Request URL is missing."));
		}

		const response = await fetch(url, {
			...options,
			credentials: "same-origin",
			headers: {
				Accept: "application/json",
				...(options.headers ?? {}),
			},
		});

		const contentType = response.headers.get("content-type") ?? "";
		let payload = {};

		if (contentType.toLowerCase().includes("application/json")) {
			payload = await response.json().catch(() => ({}));
		}

		if (!response.ok) {
			throw new Error(payload.message || `${gettext("HTTP error")} ${response.status}`);
		}

		return payload;
	};

	const debounce = (callback, delay = 300) => {
		let timeoutId;

		return (...args) => {
			window.clearTimeout(timeoutId);
			timeoutId = window.setTimeout(() => callback(...args), delay);
		};
	};

	const renderFields = (container, fields) => {
		container.replaceChildren();

		if (!Array.isArray(fields) || fields.length === 0) {
			container.textContent = gettext("No exportable fields found.");
			return;
		}

		const list = document.createElement("ul");

		list.classList.add("export-fields-grid");

		for (const field of fields) {
			const item = document.createElement("li");
			const label = document.createElement("label");
			const checkbox = document.createElement("input");
			const copy = document.createElement("span");
			const fieldLabel = document.createElement("span");
			const fieldName = document.createElement("span");

			item.classList.add("export-field-item");
			label.classList.add("export-field-option");
			copy.classList.add("export-field-copy");
			fieldLabel.classList.add("export-field-label");
			fieldName.classList.add("export-field-name");
			checkbox.type = "checkbox";
			checkbox.name = "fields";
			checkbox.value = field.name;
			checkbox.checked = field.default === true;

			if (field.translation_group) {
				checkbox.dataset.translationGroup = field.translation_group;
			}

			fieldLabel.textContent = field.label;
			fieldName.textContent = field.name;

			label.appendChild(checkbox);
			copy.appendChild(fieldLabel);

			if (field.label !== field.name) {
				copy.appendChild(fieldName);
			}

			label.appendChild(copy);

			item.appendChild(label);
			list.appendChild(item);
		}

		container.appendChild(list);
	};

	const renderParentResults = (container, parentInput, parentSearch, results) => {
		container.replaceChildren();

		if (!Array.isArray(results) || results.length === 0) {
			container.textContent = gettext("No pages found.");
			return;
		}

		const list = document.createElement("ul");

		for (const page of results) {
			const item = document.createElement("li");
			const button = document.createElement("button");
			const title = document.createElement("span");
			const path = document.createElement("span");

			button.type = "button";
			button.classList.add("export-parent-result");
			title.classList.add("export-parent-result__title");
			path.classList.add("export-parent-result__path");
			title.textContent = `${page.title} #${page.id}`;
			path.textContent = page.path;
			button.appendChild(title);
			button.appendChild(path);

			button.addEventListener("click", () => {
				parentInput.value = page.id;
				parentSearch.value = page.title;
				container.replaceChildren();
			});

			item.appendChild(button);
			list.appendChild(item);
		}

		container.appendChild(list);
	};

	const initializeExportForm = () => {
		const form = document.getElementById("madloba-export-form");

		if (!form || form.dataset.initialized === "true") {
			return;
		}

		const pageType = form.querySelector("#id_page_type");
		const fieldsContainer = form.querySelector("#export-fields");
		const parentSearch = form.querySelector("#id_parent_search");
		const parentInput = form.querySelector("#id_parent_id");
		const parentResults = form.querySelector("#parent-search-results");
		const submitButton = form.querySelector('button[type="submit"]');
		const selectAllFieldsButton = form.querySelector("#export-fields-select-all");
		const clearFieldsButton = form.querySelector("#export-fields-clear");
		const fieldsCount = form.querySelector("#export-fields-count");
		const progress = document.getElementById("export-progress");
		const progressIndicator = progress?.querySelector(".progress");
		const progressBar = progress?.querySelector(".bar");
		const progressStatus = document.getElementById("export-progress-status");
		const downloadLink = document.getElementById("export-download-link");

		if (
			!pageType ||
			!fieldsContainer ||
			!parentSearch ||
			!parentInput ||
			!parentResults ||
			!submitButton ||
			!selectAllFieldsButton ||
			!clearFieldsButton ||
			!fieldsCount ||
			!progress ||
			!progressIndicator ||
			!progressBar ||
			!progressStatus ||
			!downloadLink
		) {
			console.error(gettext("Export form elements were not found."));
			return;
		}

		const fieldsUrl = form.dataset.fieldsUrl;
		const parentSearchUrl = form.dataset.parentSearchUrl;
		const startUrl = form.dataset.startUrl;
		const progressUrl = form.dataset.progressUrl;
		const csrfToken = form.dataset.csrf;

		if (!fieldsUrl || !parentSearchUrl || !startUrl || !progressUrl) {
			console.error(gettext("Export endpoint URLs were not provided."));
			return;
		}

		form.dataset.initialized = "true";

		const getFieldCheckboxes = () => [...fieldsContainer.querySelectorAll('input[name="fields"]')];

		const updateFieldSelectionButtons = () => {
			const checkboxes = getFieldCheckboxes();
			const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;

			selectAllFieldsButton.disabled = checkboxes.length === 0 || selectedCount === checkboxes.length;
			clearFieldsButton.disabled = selectedCount === 0;
			fieldsCount.textContent = checkboxes.length > 0 ? `${selectedCount} / ${checkboxes.length}` : "";
		};

		const setAllFieldsSelected = (selected) => {
			for (const checkbox of getFieldCheckboxes()) {
				checkbox.checked = selected;
			}

			updateFieldSelectionButtons();
		};

		const selectAllFieldLocalizations = (checkbox) => {
			const translationGroup = checkbox.dataset.translationGroup;

			if (!checkbox.checked || !translationGroup) {
				return;
			}

			const groupCheckboxes = getFieldCheckboxes().filter(
				(groupCheckbox) => groupCheckbox.dataset.translationGroup === translationGroup,
			);
			const selectedGroupCheckboxes = groupCheckboxes.filter((groupCheckbox) => groupCheckbox.checked);

			if (selectedGroupCheckboxes.length !== 1) {
				return;
			}

			for (const groupCheckbox of groupCheckboxes) {
				groupCheckbox.checked = true;
			}
		};

		const setProgress = (percent, status) => {
			const normalizedPercent = Math.max(0, Math.min(100, Number(percent) || 0));

			progress.hidden = false;
			progressIndicator.style.opacity = "1";
			progressBar.style.width = `${normalizedPercent}%`;
			progressBar.textContent = `${normalizedPercent}%`;
			progressStatus.textContent = status;
		};

		const pollProgress = async (jobId) => {
			try {
				const url = progressUrl.replace("__JOB_ID__", encodeURIComponent(jobId));
				const payload = await requestJSON(url);

				setProgress(payload.progress, `${payload.processed ?? 0} / ${payload.total ?? 0}`);

				if (payload.status === "done") {
					downloadLink.href = payload.download_url;
					downloadLink.hidden = false;
					submitButton.disabled = false;
					return;
				}

				if (payload.status === "error") {
					progressStatus.textContent = payload.message || gettext("Export failed.");
					submitButton.disabled = false;
					return;
				}

				window.setTimeout(() => {
					pollProgress(jobId);
				}, 1000);
			} catch (error) {
				progressStatus.textContent = error instanceof Error ? error.message : gettext("Export failed.");
				submitButton.disabled = false;
			}
		};

		pageType.addEventListener("change", async () => {
			parentInput.value = "";
			parentSearch.value = "";
			parentResults.replaceChildren();
			downloadLink.hidden = true;

			if (!pageType.value) {
				fieldsContainer.textContent = gettext("Choose page type first.");
				updateFieldSelectionButtons();
				return;
			}

			fieldsContainer.textContent = gettext("Loading fields...");
			updateFieldSelectionButtons();

			try {
				const url = new URL(fieldsUrl, window.location.origin);

				url.searchParams.set("page_type", pageType.value);

				const payload = await requestJSON(url.toString());

				renderFields(fieldsContainer, payload.fields);
				updateFieldSelectionButtons();
			} catch (error) {
				fieldsContainer.textContent = error instanceof Error ? error.message : gettext("Could not load fields.");
				updateFieldSelectionButtons();
			}
		});

		fieldsContainer.addEventListener("change", (event) => {
			if (event.target instanceof HTMLInputElement && event.target.name === "fields") {
				selectAllFieldLocalizations(event.target);
				updateFieldSelectionButtons();
			}
		});

		selectAllFieldsButton.addEventListener("click", () => {
			setAllFieldsSelected(true);
		});

		clearFieldsButton.addEventListener("click", () => {
			setAllFieldsSelected(false);
		});

		parentSearch.addEventListener(
			"input",
			debounce(async () => {
				parentInput.value = "";

				const query = parentSearch.value.trim();

				if (!pageType.value || query.length < 2) {
					parentResults.replaceChildren();
					return;
				}

				parentResults.textContent = gettext("Searching...");

				try {
					const url = new URL(parentSearchUrl, window.location.origin);

					url.searchParams.set("page_type", pageType.value);
					url.searchParams.set("q", query);

					const payload = await requestJSON(url.toString());

					renderParentResults(parentResults, parentInput, parentSearch, payload.results);
				} catch (error) {
					parentResults.textContent = error instanceof Error ? error.message : gettext("Search failed.");
				}
			}),
		);

		form.addEventListener("submit", async (event) => {
			event.preventDefault();

			const selectedFields = [...form.querySelectorAll('input[name="fields"]:checked')].map((input) => input.value);

			if (!pageType.value) {
				progressStatus.textContent = gettext("Choose a page type.");
				progress.hidden = false;
				return;
			}

			if (selectedFields.length === 0) {
				progressStatus.textContent = gettext("Choose at least one field.");
				progress.hidden = false;
				return;
			}

			submitButton.disabled = true;
			downloadLink.hidden = true;
			setProgress(0, gettext("Starting export..."));

			try {
				const payload = await requestJSON(startUrl, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						"X-CSRFToken": csrfToken,
					},
					body: JSON.stringify({
						page_type: pageType.value,
						fields: selectedFields,
						filters: {
							created_from: form.querySelector("#id_created_from")?.value ?? "",
							created_to: form.querySelector("#id_created_to")?.value ?? "",
							updated_from: form.querySelector("#id_updated_from")?.value ?? "",
							updated_to: form.querySelector("#id_updated_to")?.value ?? "",
							parent_id: parentInput.value,
							live: form.querySelector("#id_live")?.value ?? "",
						},
					}),
				});

				if (!payload.job_id) {
					throw new Error(gettext("Server did not return an export job ID."));
				}

				await pollProgress(payload.job_id);
			} catch (error) {
				progressStatus.textContent = error instanceof Error ? error.message : gettext("Could not start export.");
				submitButton.disabled = false;
			}
		});
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initializeExportForm);
	} else {
		initializeExportForm();
	}
})();
