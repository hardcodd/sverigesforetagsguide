window.MadlobaAdminCsvImport = Object.freeze({
	downloadImportResults: (originalFile, fields, rows, results, delimiter, newline) => {
		const sourceFields = fields.filter((field) => field !== "success" && field !== "message");
		const outputFields = ["success", "message", ...sourceFields];
		const outputData = rows.map((row, index) => [
			results[index]?.success === true,
			results[index]?.message ?? "",
			...sourceFields.map((field) => row[field] ?? ""),
		]);

		// BOM makes UTF-8 text open correctly in Excel as well.
		const csv = `\uFEFF${window.Papa.unparse({ fields: outputFields, data: outputData }, { delimiter, newline })}`;
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
	},
});
