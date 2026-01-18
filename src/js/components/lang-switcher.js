(() => {
	document.querySelectorAll(".lang-switcher").forEach((el) => {
		el.addEventListener("click", () => {
			if (el.classList.contains("show")) return;
			el.classList.add("show");
		});
	});

	document.addEventListener("click", (e) => {
		if (!e.target.closest(".lang-switcher")) {
			document.querySelectorAll(".lang-switcher").forEach((el) => {
				el.classList.remove("show");
			});
		}
	});
})();
