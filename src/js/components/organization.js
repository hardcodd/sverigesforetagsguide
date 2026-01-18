import tippy from "tippy.js";
import ClipboardJS from "clipboard";

(() => {
	function copyToClipboard(containerSelector, btnSelector, inputSelector, successMsg, errorMsg) {
		const container = document.querySelector(containerSelector);
		if (!container) return;

		const copyBtn = container.querySelector(btnSelector);
		const copyInput = container.querySelector(inputSelector);

		const clipboard = new ClipboardJS(copyBtn, {
			text: () => copyInput.value,
		});

		clipboard.on("success", () => {
			const instance = tippy(copyBtn, {
				content: successMsg,
			});
			instance.show();
			setTimeout(() => {
				instance.destroy();
			}, 2000);
		});

		clipboard.on("error", () => {
			const instance = tippy(copyBtn, {
				content: errorMsg,
			});
			instance.show();
			setTimeout(() => {
				instance.destroy();
			}, 2000);
		});
	}

	// Copy website links to clipboard
	copyToClipboard(
		".organization__website-links",
		".copy-link__btn",
		'input[name="link"]',
		gettext("Link copied!"),
		gettext("Failed to copy the link!"),
	);

	// Copy coordinates to clipboard
	copyToClipboard(
		".organization__coords",
		".copy-coords__btn",
		'input[name="coords"]',
		gettext("Coordinates copied!"),
		gettext("Failed to copy coordinates!"),
	);

	// Copy plus code to clipboard
	copyToClipboard(
		".organization__plus-code",
		".copy-plus-code__btn",
		'input[name="plus-code"]',
		gettext("Plus code copied!"),
		gettext("Failed to copy plus code!"),
	);

	// Phone numbers
	(() => {
		const container = document.querySelector(".organization__phones-list");
		if (!container) return;

		const cta = document.querySelector(".phones__cta");

		container.querySelectorAll("li").forEach((li) => {
			const excerpt = li.querySelector(".phone-number__excerpt");
			const number = li.querySelector(".phone-number");

			excerpt.addEventListener("click", () => {
				excerpt.classList.add("hidden");
				number.classList.remove("hidden");
				cta.classList.remove("hidden");
			});
		});
	})();

	// Folding sections
	(() => {
		document.querySelectorAll(".organization-block").forEach((block) => {
			const header = block.querySelector(".organization-block__title[target]");
			if (!header) return;

			const target = block.querySelector(header.getAttribute("target"));
			if (!target) return;

			header.innerHTML += require("@icons/chevron-down.svg").default;
			header.classList.add("clickable");

			header.addEventListener("click", () => {
				target.classList.toggle("hidden");
				header.classList.toggle("active");
			});
		});
	})();
})();
