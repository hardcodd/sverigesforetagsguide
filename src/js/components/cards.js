import Swiper from "swiper";
import { Navigation, Mousewheel, Autoplay } from "swiper/modules";

document.querySelectorAll(".cards-carousel, .reviews-carousel").forEach((carousel) => {
	const slidesPerView = carousel.getAttribute("data-slides-per-view");

	const slidesPerViewLg = slidesPerView ? slidesPerView : 4;

	let slidesPerViewMd = slidesPerViewLg - 1;
	slidesPerViewMd = slidesPerViewMd > 0 ? slidesPerViewMd : 1;

	let slidesPerViewSm = slidesPerViewMd - 1;
	slidesPerViewSm = slidesPerViewSm > 0 ? slidesPerViewSm : 1;

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
				slidesPerView: slidesPerViewSm,
			},
			1024: {
				slidesPerView: slidesPerViewMd,
			},
			1200: {
				slidesPerView: slidesPerViewLg,
			},
		},
	});
});
