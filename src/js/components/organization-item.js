import { setColorToElement, getColorFromImage } from "../utils";
import Swiper from "swiper";
import { Navigation, Mousewheel, Autoplay } from "swiper/modules";

(() => {
	const organizationItems = document.querySelectorAll(".organization-item");

	organizationItems.forEach((organization) => {
		const image = organization.querySelector(".organization-item__thumb img");
		if (!image) return;

		function setOrganizationColor() {
			// check if image is loaded
			if (!image.complete) {
				image.addEventListener("load", setOrganizationColor);
				return;
			}

			setColorToElement(organization, getColorFromImage(image), 0.1, 0.2);
		}

		setOrganizationColor();
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
