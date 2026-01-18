(() => {
	const tabs = document.querySelectorAll(".contact-tabs li");
	const tabButtons = document.querySelectorAll(".contact-tabs-filter li");

	if (!tabs) return;

	tabButtons.forEach((button) => {
		tabButtons.forEach((btn) => btn.classList.remove("active"));
		tabButtons[0].classList.add("active");

		tabs.forEach((tab) => tab.classList.add("hidden"));
		tabs[0].classList.remove("hidden");

		button.addEventListener("click", () => {
			const target = button.getAttribute("data-target");
			tabButtons.forEach((btn) => btn.classList.remove("active"));
			button.classList.add("active");
			tabs.forEach((tab) => tab.classList.add("hidden"));
			tabs.forEach((tab) => {
				if (tab.getAttribute("id") === target) {
					tab.classList.remove("hidden");
				}
			});
		});
	});
})();
