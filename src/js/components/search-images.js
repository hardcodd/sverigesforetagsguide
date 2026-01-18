import { setColorToElement, getColorFromImage } from "../utils";

(() => {
	const searchResultItems = document.querySelectorAll(".search-item");

	searchResultItems.forEach((searchResult) => {
		const image = searchResult.querySelector(".search-item__thumb img");
		if (!image) return;

		function setsearchResultColor() {
			// check if image is loaded
			if (!image.complete) {
				image.addEventListener("load", setsearchResultColor);
				return;
			}

			setColorToElement(searchResult, getColorFromImage(image), 0.1, 0.2);
		}

		setsearchResultColor();
	});
})();
