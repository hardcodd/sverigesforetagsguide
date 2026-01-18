import Swiper from "swiper";
import { Pagination, Autoplay } from "swiper/modules";
import { setColorToElement, getColorFromImage } from "../utils";

(() => {
	if (!document.querySelector(".template-catalog-organization") || !document.querySelector(".organization__images")) {
		return;
	}

	const swiper = new Swiper(".organization__images", {
		modules: [Pagination, Autoplay],
		loop: true,
		effect: "cards",
		init: false,
		pagination: {
			el: ".swiper-pagination",
			clickable: true,
		},
		autoplay: {
			delay: 10000,
		},
	});

	function getActiveImage() {
		let image = document.querySelector(".organization__images .swiper-slide-active .swiper-slide-thumb img");
		if (!image) {
			image = document.querySelector(".organization__images .swiper-slide-thumb img");
		}
		return image;
	}

	function setImagesColor() {
		const image = getActiveImage();
		if (!image) return;

		// check if image is loaded
		if (!image.complete) {
			image.addEventListener("load", setImagesColor);
			return;
		}

		setColorToElement(document.querySelector(".organization__images"), getColorFromImage(image));
	}

	swiper.on("afterInit", () => {
		setTimeout(setImagesColor, 100);
	});

	swiper.on("slideChangeTransitionEnd", setImagesColor);

	swiper.init();
})();
