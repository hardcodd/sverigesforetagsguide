import "mburger-webcomponent";

export default class Navigation {
	/**
	 * Features:
	 * 1. Add burger icon to open/close menu
	 * 2. Add icons to items those have submenu
	 * 3. Close menu on anchor click
	 * 4. Close menu on backdrop click
	 * 5. Close menu on resize
	 *
	 * @example new Navigation(document.querySelector(".navigation"))
	 * @example new Navigation(document.querySelector(".navigation"), {mmEnabled: false})
	 */
	constructor(
		instance = undefined,
		{
			burger = document.querySelector("mm-burger"),
			burgerActiveClass = "active",
			breakpoint = 992,
			dropDownMenuIcon = '<i class="md-chevron-down"></i>',
			dropDownSubMenuIcon = '<i class="md-chevron-right"></i>',
			mmEnabled = true,
			mmSelected = "Selected",
			mmSlidingSubmenus = true,
			mmTitle = "Menu",
			mmTheme = "light",
			mmPosition = "left",
		} = {},
	) {
		this.instance = instance;

		if (!this.instance) return;

		const userAgentContext = parseInt(getComputedStyle(document.querySelector("html")).fontSize) / 16;

		this.burger = burger;
		this.burgerActiveClass = burgerActiveClass;
		this.breakpoint = breakpoint * userAgentContext;
		this.dropDownMenuIcon = dropDownMenuIcon;
		this.dropDownSubMenuIcon = dropDownSubMenuIcon;
		this.mmEnabled = mmEnabled;
		this.selected = mmSelected;
		this.slidingSubmenus = mmSlidingSubmenus;
		this.title = mmTitle;
		this.theme = mmTheme;
		this.position = mmPosition;
		this.mediaQuery = `(max-width: ${breakpoint / 16}rem)`;

		this.isOpen = false;

		this.#submenusHandler();

		this.#MmenuInit();
	}

	#MmenuInit() {
		if (!this.mmEnabled) return;

		this.#displayBurger();

		const MmenuLight = require("mmenu-light").default;

		this.mmenu = new MmenuLight(this.instance, this.mediaQuery);

		this.mmenu.navigation({
			selected: this.selected,
			slidingSubmenus: this.slidingSubmenus,
			title: this.title,
			theme: this.theme,
		});

		this.drawer = this.mmenu.offcanvas({
			position: this.position,
		});

		// Close mmenu on anchor click
		this.instance.querySelectorAll('[href^="#"]').forEach((a) => {
			if (a.getAttribute("href") !== "#") {
				a.addEventListener("click", () => {
					this.#burgerState(false);
					this.drawer.close();
				});
			}
		});

		// Toggle mmenu on burger click
		this.burger.addEventListener("click", () => {
			this.isOpen = !this.isOpen;

			if (this.isOpen) {
				this.#burgerState(true);
				this.drawer.open();
			} else {
				this.#burgerState(false);
				this.drawer.close();
			}
		});

		// Reset burger state on backdrop click
		this.drawer.backdrop.addEventListener("click", () => {
			this.#burgerState(false);
		});

		// Reset burger state on resize
		window.addEventListener("resize", () => {
			if (window.innerWidth > this.breakpoint) {
				this.#burgerState(false);
			}
		});
	}

	// Activate or Deactivate burger
	#burgerState(active = false) {
		this.isOpen = active;
		this.burger.state = active ? "cross" : "bars";
		if (active) {
			this.burger.classList.add(this.burgerActiveClass);
		} else {
			this.burger.classList.remove(this.burgerActiveClass);
		}
	}

	#displayBurger() {
		const displayBurger = () => {
			if (window.innerWidth <= this.breakpoint) {
				this.burger.style.display = "block";
			} else {
				this.burger.style.display = "none";
			}
		};
		displayBurger();
		window.addEventListener("resize", displayBurger);
	}

	#submenusHandler() {
		// Add arrow to items those have submenu
		const items = this.instance.querySelectorAll("li");

		items.forEach((li) => {
			if (li.querySelector("ul")) {
				const icon = li.parentNode.parentNode.tagName === "LI" ? this.dropDownSubMenuIcon : this.dropDownMenuIcon;
				li.querySelector("a").innerHTML += `<span class="submenu-icon">${icon}</span>`;
			}
		});
	}
}
