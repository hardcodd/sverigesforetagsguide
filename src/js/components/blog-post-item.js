import { setColorToElement, getColorFromImage } from "../utils";

(() => {
	const postItems = document.querySelectorAll(".blog-post:not([class*='detail'])");

	postItems.forEach((post) => {
		const image = post.querySelector(".blog-post__image img");
		if (!image) return;

		function setPostColor() {
			// check if image is loaded
			if (!image.complete) {
				image.addEventListener("load", setPostColor);
				return;
			}

			setColorToElement(post, getColorFromImage(image), 0.2);
		}

		setPostColor();
	});
})();
