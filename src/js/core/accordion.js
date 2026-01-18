import { slideDown, slideUp } from "./dom-slider";

export default class Accordion {
	/**
	 * Accordion
	 *
	 * @example import Accordion from "./components/accordion";
	 * new Accordion(document.querySelector(".accordion"), {...});
	 */
	constructor(
		instance,
		{
			openFirst = true,
			enableMultiple = false,
			panesClass = "accordion__pane",
			contentClass = "accordion__content",
			contentWrapperClass = "accordion__content-wrapper",
			paneActiveClass = "accordion__pane--active",
			headingsClass = "accordion__heading",
			openIcon = '<i class="md-plus"></i>',
			closeIcon = '<i class="md-minus"></i>',
			iconClass = "accordion__icon",
			duration = 400,
			easing = "ease",
		} = {},
	) {
		this.instance = instance;
		this.openFirst = openFirst;
		this.enableMultiple = enableMultiple;
		this.headingsClass = `.${headingsClass}`;
		this.panesClass = `.${panesClass}`;
		this.contentClass = `.${contentClass}`;
		this.contentWrapperClass = contentWrapperClass;
		this.paneActiveClass = paneActiveClass;
		this.iconClass = iconClass;
		this.openIcon = this.#openIcon(openIcon);
		this.closeIcon = this.#closeIcon(closeIcon);
		this.lock = false;
		this.duration = duration;
		this.easing = easing;

		if (this.instance) {
			this.panes = this.instance.querySelectorAll(this.panesClass);
			if (this.panes.length) this.#init();
		}
	}

	#init() {
		this.panes.forEach((pane, i) => {
			const heading = pane.querySelector(this.headingsClass);
			const content = pane.querySelector(this.contentClass);

			content.innerHTML = `<div class="${this.contentWrapperClass}">${content.innerHTML}</div>`;

			if (i === 0 && this.openFirst) {
				pane.classList.add(this.paneActiveClass);
				this.#setCloseIcon(heading);
				slideDown(content, {
					duration: 0,
					easing: "ease",
				});
			} else {
				this.#setOpenIcon(heading);
				slideUp(content, {
					duration: 0,
					easing: "ease",
				});
			}

			heading.addEventListener("click", (e) => {
				e.preventDefault();

				if (this.lock) return;

				this.lock = true;

				if (pane.classList.contains(this.paneActiveClass)) {
					if (this.enableMultiple) this.#closeActive(pane);
					else this.#closeAllActive();

					const content = pane.querySelector(this.contentClass);
					slideUp(content, {
						duration: this.duration,
						easing: this.easing,
					});

					setTimeout(() => (this.lock = false), this.duration);
				} else if (!pane.classList.contains(this.paneActiveClass)) {
					if (!this.enableMultiple) this.#closeAllActive();

					this.#setCloseIcon(heading);
					pane.classList.add(this.paneActiveClass);

					const content = pane.querySelector(this.contentClass);
					slideDown(content, {
						duration: this.duration,
						easing: this.easing,
					});

					setTimeout(() => (this.lock = false), this.duration);
				}
			});
		});
	}

	#closeAllActive() {
		this.panes.forEach((pane) => {
			if (pane.classList.contains(this.paneActiveClass)) {
				const content = pane.querySelector(this.contentClass);
				slideUp(content, {
					duration: this.duration,
					easing: this.easing,
				});

				pane.classList.remove(this.paneActiveClass);
				const heading = pane.querySelector(this.headingsClass);

				this.#setOpenIcon(heading);
			}
		});
	}

	#closeActive(pane) {
		const content = pane.querySelector(this.contentClass);
		slideUp(content, {
			duration: this.duration,
			easing: this.easing,
		});

		pane.classList.remove(this.paneActiveClass);
		const heading = pane.querySelector(this.headingsClass);

		this.#setOpenIcon(heading);
	}

	#openIcon(icon) {
		return `<span class="${this.iconClass} ${this.iconClass}--open">${icon}</span>`;
	}

	#closeIcon(icon) {
		return `<span class="${this.iconClass} ${this.iconClass}--close">${icon}</span>`;
	}

	#setOpenIcon(heading) {
		this.#removeAnyIcon(heading);
		heading.innerHTML += this.openIcon;
	}

	#setCloseIcon(heading) {
		this.#removeAnyIcon(heading);
		heading.innerHTML += this.closeIcon;
	}

	#removeAnyIcon(heading) {
		const toRemove = heading.querySelector(`[class*="${this.iconClass}"]`);
		if (toRemove) toRemove.remove();
	}
}
