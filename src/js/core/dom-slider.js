function setElementStyle(element, styles = {}) {
	for (const [property, value] of Object.entries(styles)) {
		element.style.setProperty(property, value);
	}
}

function clearElementStyle(element, properties = []) {
	for (const property of properties) {
		element.style.removeProperty(property);
	}
}

function slideDown(element, { duration = 400, easing = "ease", delay = 0, display = "block" } = {}) {
	if (!element || element.lock || window.getComputedStyle(element).display !== "none") return;

	element.lock = true;
	element.style.display = display;

	const computedStyle = window.getComputedStyle(element);
	const height = computedStyle.height;
	const paddingTop = computedStyle.paddingTop;
	const paddingBottom = computedStyle.paddingBottom;
	const borderTopWidth = computedStyle.borderTopWidth;
	const borderBottomWidth = computedStyle.borderBottomWidth;

	setElementStyle(element, {
		overflow: "hidden",
		height: 0,
		paddingTop: 0,
		paddingBottom: 0,
		borderTopWidth: 0,
		borderBottomWidth: 0,
	});

	element.style.transition = `all ${duration}ms ${easing}`;

	setTimeout(
		() => {
			setElementStyle(element, {
				height: height,
				paddingTop: paddingTop,
				paddingBottom: paddingBottom,
				borderTopWidth: borderTopWidth,
				borderBottomWidth: borderBottomWidth,
			});
		},
		delay > 20 ? delay : 20
	);

	setTimeout(() => {
		clearElementStyle(element, [
			"transition",
			"height",
			"overflow",
			"padding-top",
			"padding-bottom",
			"border-top-width",
			"border-bottom-width",
		]);
		element.lock = false;
	}, duration + (delay > 20 ? delay : 20));
}

function slideUp(element, { duration = 400, easing = "ease", delay = 0 } = {}) {
	if (!element || element.lock || window.getComputedStyle(element).display === "none") return;

	element.lock = true;
	const computedStyle = window.getComputedStyle(element);

	setElementStyle(element, {
		height: computedStyle.height,
		overflow: "hidden",
		transition: `all ${duration}ms ${easing}`,
	});

	setTimeout(
		() => {
			setElementStyle(element, {
				height: 0,
				paddingTop: 0,
				paddingBottom: 0,
				borderTopWidth: 0,
				borderBottomWidth: 0,
			});
		},
		delay > 20 ? delay : 20
	);

	setTimeout(() => {
		element.style.display = "none";
		clearElementStyle(element, [
			"transition",
			"height",
			"overflow",
			"padding-top",
			"padding-bottom",
			"border-top-width",
			"border-bottom-width",
		]);
		element.lock = false;
	}, duration + (delay > 20 ? delay : 20));
}

function slideToggle(element, { duration = 400, easing = "ease", delay = 0, display = "block" } = {}) {
	if (!element || element.lock) return;

	const isHidden = window.getComputedStyle(element).display === "none";
	if (isHidden) {
		slideDown(element, { duration, easing, delay, display });
	} else {
		slideUp(element, { duration, easing, delay });
	}
}

export { slideDown, slideUp, slideToggle };
