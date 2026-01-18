(() => {
	const textareas = document.querySelectorAll("textarea");
	if (!textareas.length) return;

	function setHeight(textarea) {
		textarea.style.height = "auto";
		textarea.style.minHeight = "auto";
		textarea.style.height = `${textarea.scrollHeight / 16}rem`;
		textarea.style.minHeight = `${textarea.scrollHeight / 16}rem`;
	}

	textareas.forEach((textarea) => {
		textarea.setAttribute("rows", 1);
		textarea.style.overflow = "hidden";
		textarea.style.resize = "none";
		textarea.style.appearance = "none";
		setHeight(textarea);

		textarea.addEventListener("input", () => {
			setHeight(textarea);
		});

		// Disable first empty line
		textarea.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && textarea.value === "") {
				e.preventDefault();
			}
		});

		// Disable double empty line
		textarea.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && textarea.value.slice(-1) === "\n") {
				const lines = textarea.value.split("\n");
				if (lines.length > 1 && lines[lines.length - 2] === "") {
					e.preventDefault();
				}
			}
		});
	});
})();
