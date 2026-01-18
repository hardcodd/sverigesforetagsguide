// Body padding top for fixed header
(() => {
	const header = document.querySelector(".header");
	if (!header) return;

	function setBodyPaddingTop() {
		document.body.style.paddingTop = `${header.offsetHeight}px`;
	}

	setBodyPaddingTop();
	window.addEventListener("load", setBodyPaddingTop);
	const observer = new ResizeObserver(setBodyPaddingTop);
	observer.observe(header);
})();

// Hide bottom header when footer in viewport
(() => {
	const bottomHeader = document.querySelector(".bottom-header");
	const footer = document.querySelector(".footer");
	if (!bottomHeader || !footer) return;

	const observer = new IntersectionObserver((entries) => {
		entries.forEach((entry) => {
			if (entry.isIntersecting) {
				bottomHeader.classList.add("hidden");
			} else {
				bottomHeader.classList.remove("hidden");
			}
		});
	});

	observer.observe(footer);
})();

// Header scroll indicator
(() => {
	const header = document.querySelector(".header");
	if (!header) return;

	const indicator = document.createElement("div");
	indicator.className = "header__scroll-indicator";
	header.appendChild(indicator);

	function setIndicatorWidth() {
		indicator.style.width = `${(window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100}%`;
	}

	document.addEventListener("scroll", setIndicatorWidth);
	window.addEventListener("resize", setIndicatorWidth);
})();
