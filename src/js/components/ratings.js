import Swiper from "swiper";
import { Pagination, Autoplay } from "swiper/modules";

new Swiper(".rating-gallery", {
	modules: [Pagination, Autoplay],
	slidesPerView: 3,
	loop: true,
	spaceBetween: 10,
	pagination: {
		el: ".swiper-pagination",
		clickable: true,
	},
	autoplay: {
		delay: 5000,
	},
	breakpoints: {
		320: {
			slidesPerView: 1,
		},
		768: {
			slidesPerView: 2,
		},
		1024: {
			slidesPerView: 3,
		},
	},
});
