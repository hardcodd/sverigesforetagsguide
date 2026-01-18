(() => {
	document.querySelectorAll(".tabs").forEach((tabs) => {
		const tabsList = tabs.querySelector(".tabs__list");
		const tabsItems = tabsList.querySelectorAll("li");
		const tabsContents = tabs.querySelector(".tabs__content");
		const arrowLeftContainer = tabs.querySelector(".tabs__arrow--left");
		const arrowRightContainer = tabs.querySelector(".tabs__arrow--right");
		const arrowLeft = arrowLeftContainer.querySelector("svg");
		const arrowRight = arrowRightContainer.querySelector("svg");

		const scrollDistance = 200; // How much to scroll on arrow click
		const snapDistance = 50; // Distance to snap on scroll

		// Scroll to start on load
		tabsList.scrollTo(0, 0);

		// Helper function to clear active tabs
		function clearActive() {
			tabsItems.forEach((item) => {
				item.classList.remove("active");
			});
			tabsContents.querySelectorAll("[id^='tab-']").forEach((content) => {
				content.classList.remove("active");
			});
		}

		// Helper function to get current tabsList scroll position
		function getScrollPosition(ceil = true) {
			return ceil ? Math.ceil(tabsList.scrollLeft) : tabsList.scrollLeft;
		}

		// Helper function to get max scroll width
		function getMaxScroll() {
			return tabsList.scrollWidth - tabsList.clientWidth;
		}

		// Helper function to get scrolling direction
		function scrollDirectionTracker() {
			let lastScrollPosition = 0;

			return function () {
				const currentScrollPosition = getScrollPosition(false);
				const direction = currentScrollPosition > lastScrollPosition ? "right" : "left";
				lastScrollPosition = currentScrollPosition;
				return direction;
			};
		}

		// Helper function isScrollable
		function isScrollable() {
			return tabsList.scrollWidth > tabsList.clientWidth;
		}

		// Function to scroll to active tab
		function scrollToActive() {
			const activeTab = tabsList.querySelector(".active");
			const activeTabPosition = activeTab.offsetLeft;
			const activeTabWidth = activeTab.offsetWidth;
			const activeTabCenter = activeTabPosition + activeTabWidth / 2;
			const tabsListCenter = tabsList.offsetWidth / 2;
			const scrollPosition = activeTabCenter - tabsListCenter;

			tabsList.scrollLeft = scrollPosition;
		}

		// Function to show or hide arrows based on scroll position
		function handleArrowsVisibility() {
			if (getScrollPosition() > 0) {
				arrowLeftContainer.classList.add("active");
			} else {
				arrowLeftContainer.classList.remove("active");
			}

			if (getScrollPosition() < getMaxScroll()) {
				arrowRightContainer.classList.add("active");
			} else {
				arrowRightContainer.classList.remove("active");
			}
		}

		// Make first tab active on load
		tabsItems[0].classList.add("active");
		tabsContents.querySelector(tabsItems[0].dataset.target).classList.add("active");

		// Handle arrows state on load
		handleArrowsVisibility();
		// Handle arrows state on scroll
		tabsList.addEventListener("scroll", handleArrowsVisibility);
		// Handle arrows state on resize
		window.addEventListener("resize", handleArrowsVisibility);

		// Snap tabs on scroll
		const scrollDirectionLeft = scrollDirectionTracker();
		const scrollDirectionRight = scrollDirectionTracker();
		tabsList.addEventListener("scroll", () => {
			if (scrollDirectionLeft() === "left" && getScrollPosition() < snapDistance) {
				tabsList.scrollTo({
					left: 0,
					behavior: "smooth",
				});
			} else if (scrollDirectionRight() === "right" && getScrollPosition() > getMaxScroll() - snapDistance) {
				tabsList.scrollTo({
					left: getMaxScroll(),
					behavior: "smooth",
				});
			}
		});

		// Handle left arrow click
		arrowLeft.addEventListener("click", () => (tabsList.scrollLeft -= scrollDistance));

		// Handle right arrow click
		arrowRight.addEventListener("click", () => (tabsList.scrollLeft += scrollDistance));

		// Handle arrow hover
		arrowLeftContainer.addEventListener("mouseenter", () => {
			tabsList.style.transform = "translateX(10px)";
		});

		arrowLeftContainer.addEventListener("mouseleave", () => {
			tabsList.style.transform = "translateX(0)";
		});

		arrowRightContainer.addEventListener("mouseenter", () => {
			tabsList.style.transform = "translateX(-10px)";
		});

		arrowRightContainer.addEventListener("mouseleave", () => {
			tabsList.style.transform = "translateX(0)";
		});

		// Make tabs scrollable by dragging
		(() => {
			let dragging = false;

			tabsList.addEventListener("mousedown", () => {
				if (!isScrollable()) return;
				dragging = true;
			});

			document.addEventListener("mouseup", () => {
				if (!dragging) return;

				tabsList.classList.remove("dragging");
				dragging = false;
			});

			document.addEventListener("mousemove", (e) => {
				if (!dragging) return;

				tabsList.classList.add("dragging");
				tabsList.scrollLeft -= e.movementX;
			});
		})();

		// Make tabs clickable
		tabsItems.forEach((item) => {
			const target = item.dataset.target;
			const content = tabs.querySelector(target);

			item.addEventListener("click", () => {
				clearActive();
				item.classList.add("active");
				content.classList.add("active");
				scrollToActive();
			});
		});
	});
})();
