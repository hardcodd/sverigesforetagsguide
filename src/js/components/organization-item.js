import { setColorToElement, getColorFromImage } from "../utils";
import Swiper from "swiper";
import { Navigation, Mousewheel, Autoplay } from "swiper/modules";

/** Apply card colors when their visible, lazy-loaded images become available. */
(() => {
	const organizationItems = document.querySelectorAll(".organization-item");

	organizationItems.forEach((organization) => {
		const image = organization.querySelector(".ratio img");
		if (!(image instanceof HTMLImageElement)) return;

		/** @returns {void} */
		function setOrganizationColor() {
			if (!image.naturalWidth) return;
			setColorToElement(organization, getColorFromImage(image), 0.1);
		}

		if (image.complete) setOrganizationColor();
		else image.addEventListener("load", setOrganizationColor, { once: true });
	});
})();

document.querySelectorAll(".organizations-carousel").forEach((carousel) => {
	new Swiper(carousel, {
		modules: [Navigation, Mousewheel, Autoplay],
		slidesPerView: 1,
		slideFullyVisibleClass: "swiper-slide--visible",
		watchSlidesProgress: true,
		autoplay: {
			delay: 5000,
		},
		navigation: {
			nextEl: ".swiper-button-next",
			prevEl: ".swiper-button-prev",
		},
		spaceBetween: 20,
		breakpoints: {
			768: {
				slidesPerView: 2,
			},
			1024: {
				slidesPerView: 3,
			},
			1200: {
				slidesPerView: 4,
			},
		},
	});
});
