/** A select-only combobox; the original select remains the form's source of truth. */
export default class OrganizationFilterSelect {
	/**
	 * Enhance a category select without changing its name, values or GET submission.
	 * @param {HTMLSelectElement} select
	 * @param {() => void} closeOthers
	 */
	constructor(select, closeOthers) {
		this.select = select;
		this.closeOthers = closeOthers;
		this.options = Array.from(select.options);
		this.activeIndex = Math.max(0, select.selectedIndex);
		this.search = "";
		this.lastTypedAt = 0;
		this.wrapper = document.createElement("div");
		this.wrapper.className = "organization-select";
		this.button = document.createElement("button");
		this.button.type = "button";
		this.button.id = `${select.id}-control`;
		this.button.className = "organization-select__trigger";
		this.button.setAttribute("role", "combobox");
		this.button.setAttribute("aria-haspopup", "listbox");
		this.button.setAttribute("aria-expanded", "false");
		this.label = document.createElement("span");
		this.button.append(this.label);
		this.menu = document.createElement("ul");
		this.menu.id = `${select.id}-options`;
		this.menu.className = "organization-select__menu";
		this.menu.setAttribute("role", "listbox");
		this.menu.hidden = true;
		this.button.setAttribute("aria-controls", this.menu.id);
		this.items = this.options.map((option, index) => {
			const item = document.createElement("li");
			item.id = `${select.id}-option-${index}`;
			item.setAttribute("role", "option");
			item.textContent = option.text;
			// Keep DOM focus on the combobox when choosing with a mouse or touch.
			item.addEventListener("pointerdown", (event) => event.preventDefault());
			item.addEventListener("pointermove", () => this.highlight(index));
			item.addEventListener("click", () => {
				this.activeIndex = index;
				this.commit();
				this.button.focus({ preventScroll: true });
			});
			this.menu.append(item);
			return item;
		});
		this.wrapper.append(this.button, this.menu);
		select.after(this.wrapper);
		for (const label of Array.from(select.labels ?? [])) {
			label.id ||= `${select.id}-label`;
			this.button.setAttribute("aria-labelledby", label.id);
			this.menu.setAttribute("aria-labelledby", label.id);
			label.htmlFor = this.button.id;
		}
		select.hidden = true;
		this.sync();
		this.button.addEventListener("click", () => (this.menu.hidden ? this.open() : this.close()));
		this.button.addEventListener("keydown", (event) => this.onKeydown(event));
		this.button.addEventListener("blur", () => {
			if (!this.menu.hidden) this.commit();
		});
		select.addEventListener("change", () => this.sync());
		document.addEventListener("pointerdown", (event) => {
			if (event.target instanceof Node && !this.wrapper.contains(event.target) && !this.menu.hidden) this.commit();
		});
	}

	/** @returns {void} */
	sync() {
		this.activeIndex = Math.max(0, this.select.selectedIndex);
		this.label.textContent = this.options[this.activeIndex]?.text ?? "";
		this.items.forEach((item, index) => {
			item.setAttribute("aria-selected", String(index === this.select.selectedIndex));
		});
	}

	/** @returns {void} */
	open() {
		this.closeOthers();
		this.sync();
		this.menu.hidden = false;
		const bounds = this.button.getBoundingClientRect();
		const spaceBelow = window.innerHeight - bounds.bottom - 80;
		const spaceAbove = bounds.top - 80;
		// Leave clearance for the site's fixed header and floating mobile navigation.
		this.wrapper.classList.toggle(
			"organization-select--up",
			spaceBelow < this.menu.offsetHeight && spaceAbove > spaceBelow,
		);
		this.button.setAttribute("aria-expanded", "true");
		this.highlight(this.activeIndex);
	}

	/** Dismiss without committing tentative keyboard navigation. @returns {void} */
	close() {
		this.menu.hidden = true;
		this.button.setAttribute("aria-expanded", "false");
		this.button.removeAttribute("aria-activedescendant");
		this.search = "";
	}

	/** @param {number} index @returns {void} */
	highlight(index) {
		this.activeIndex = Math.max(0, Math.min(index, this.items.length - 1));
		this.items.forEach((item, itemIndex) => item.classList.toggle("is-highlighted", itemIndex === this.activeIndex));
		const item = this.items[this.activeIndex];
		if (!item) return;
		this.button.setAttribute("aria-activedescendant", item.id);
		// Scroll only the list, avoiding page jumps when the popup opens.
		if (item.offsetTop < this.menu.scrollTop) this.menu.scrollTop = item.offsetTop;
		else if (item.offsetTop + item.offsetHeight > this.menu.scrollTop + this.menu.clientHeight) {
			this.menu.scrollTop = item.offsetTop + item.offsetHeight - this.menu.clientHeight;
		}
	}

	/** @returns {void} */
	commit() {
		const changed = this.select.selectedIndex !== this.activeIndex;
		this.select.selectedIndex = this.activeIndex;
		this.sync();
		this.close();
		if (changed) this.select.dispatchEvent(new Event("change", { bubbles: true }));
	}

	/** Navigate without submitting the form or committing until confirmation. @param {KeyboardEvent} event @returns {void} */
	onKeydown(event) {
		if (event.key === "Tab") {
			if (!this.menu.hidden) this.commit();
			return;
		}
		if (event.key === "Escape") {
			if (!this.menu.hidden) event.preventDefault();
			this.close();
			return;
		}
		if (event.ctrlKey || event.metaKey || (event.altKey && !["ArrowDown", "ArrowUp"].includes(event.key))) return;
		if (["Enter", " "].includes(event.key)) {
			event.preventDefault();
			if (this.menu.hidden) this.open();
			else this.commit();
			return;
		}
		if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
			event.preventDefault();
			const wasClosed = this.menu.hidden;
			if (wasClosed) this.open();
			if (event.altKey) {
				if (event.key === "ArrowUp") this.commit();
				return;
			}
			if (event.key === "Home") this.highlight(0);
			else if (event.key === "End") this.highlight(this.items.length - 1);
			else if (!wasClosed) this.highlight(this.activeIndex + (event.key === "ArrowDown" ? 1 : -1));
			return;
		}
		if (event.key.length !== 1 || event.altKey) return;
		event.preventDefault();
		if (this.menu.hidden) this.open();
		const now = Date.now();
		this.search = (now - this.lastTypedAt < 700 ? this.search : "") + event.key.toLocaleLowerCase();
		this.lastTypedAt = now;
		const repeated = Array.from(this.search).every((letter) => letter === this.search[0]);
		const prefix = repeated ? this.search[0] : this.search;
		for (let offset = 1; offset <= this.options.length; offset += 1) {
			const index = (this.activeIndex + offset) % this.options.length;
			if (this.options[index].text.toLocaleLowerCase().startsWith(prefix)) {
				this.highlight(index);
				break;
			}
		}
	}
}
