export default class LinksHandler {
	/**
	 *
	 * Features:
	 * 1. Open external links in new tab.
	 * 2. Prevent default for links with href="#"
	 * 3. Add active class to links with href equal to current url
	 * 4. Exclude links inside elements with selectors passed in exclude array
	 * 5. Observe document for new links and reinitialize handler
	 *
	 * @param {Array} exclude - Array of selectors to exclude links from handling
	 *
	 * @example new LinksHandler()
	 * @example new LinksHandler(['.pagination', '.footer-navigation'])
	 */
	constructor(exclude = []) {
		this.exclude = exclude;
		this.excludedElements = [];
		this.links = [];
		this.uri = window.location.pathname;
		this.observer = null;

		this.init();
		this.observeDocument();
	}

	init() {
		this.links = document.querySelectorAll("a[href]");
		this.#initExclude();
		this.#externalLinksHandler(this.#getExternalLinks());
		this.#preventDefaultHandler(this.#getHashLinks());
		this.#activeLinksHandler(this.#getInternalLinks());
		this.#anchorLinksHandler(this.#getInternalLinks());
	}

	#initExclude() {
		this.excludedElements = this.exclude.flatMap((selector) => {
			return [...document.querySelectorAll(`${selector}`), ...document.querySelectorAll(`${selector} a[href]`)];
		});
	}

	#externalLinksHandler(links) {
		links.forEach((link) => {
			const rel = link.getAttribute("rel");
			if (rel) {
				if (!rel.includes("noopener")) {
					link.setAttribute("rel", `${rel} noopener`);
				}
				if (!rel.includes("noreferrer")) {
					link.setAttribute("rel", `${rel} noreferrer`);
				}
			} else {
				link.setAttribute("rel", "noopener noreferrer");
			}
			link.setAttribute("target", "_blank");
			// Adding ARIA label for accessibility
			if (!link.getAttribute("aria-label")) {
				link.setAttribute("aria-label", "Opens in new tab");
			}
		});
	}

	#preventDefaultHandler(links) {
		links.forEach((link) => {
			link.addEventListener("click", (e) => e.preventDefault());
		});
	}

	#activeLinksHandler(links) {
		links.forEach((link) => {
			const linkUri = link.getAttribute("href").split("?")[0];
			if ((this.uri.includes(linkUri) && linkUri !== "/") || this.uri === linkUri) {
				link.classList.add("active");
				link.closest("li")?.classList.add("active");
			}
		});
	}

	#anchorLinksHandler(links) {
		links.forEach((link) => {
			const hash = link.getAttribute("href");
			if (hash && hash.startsWith("#") && hash.length > 1) {
				link.addEventListener("click", (e) => {
					e.preventDefault();
					const targetElement = document.querySelector(hash);
					if (targetElement) {
						const headerOffset = 100; // Adjust this value based on your fixed header height
						const y = targetElement.getBoundingClientRect().top + window.scrollY - headerOffset;
						window.scrollTo({ top: y, behavior: "smooth" });
					}
				});
			}
		});
	}

	#getExternalLinks() {
		return Array.from(this.links).filter(
			(link) => link.hostname !== window.location.hostname && !this.excludedElements.includes(link),
		);
	}

	#getHashLinks() {
		return Array.from(this.links).filter(
			(link) => link.getAttribute("href") === "#" && !this.excludedElements.includes(link),
		);
	}

	#getInternalLinks() {
		return Array.from(this.links).filter(
			(link) => link.hostname === window.location.hostname && !this.excludedElements.includes(link),
		);
	}

	observeDocument() {
		const config = { childList: true, subtree: true };
		const callback = (mutationsList, _) => {
			for (const mutation of mutationsList) {
				if (mutation.type === "childList") {
					this.init(); // Reinitialize to handle new links
				}
			}
		};
		this.observer = new MutationObserver(callback);
		this.observer.observe(document.body, config);
	}

	// Call this method when you no longer need to observe changes
	disconnectObserver() {
		if (this.observer) {
			this.observer.disconnect();
		}
	}
}
