import LinksHandler from "./core/links";
import Accordion from "./core/accordion";
import tippy, { followCursor } from "tippy.js";
import { Fancybox } from "@fancyapps/ui";
import { isTouchDevice } from "./utils";

// Components
import "./components/header";
import "./components/header-search";
import "./components/lang-switcher";
import "./components/tabs";
import "./components/organization-images";
import "./components/search-images";
import "./components/organization";
import "./components/organization-item";
import "./components/textarea";
import "./components/images-upload-field";
import "./components/reviews";
import "./components/ratings";
import "./components/blog-post-item";
import "./components/cards";
import "./components/cookie-consent";
import "./components/comments";
import "./components/contact-tabs";
import "./components/blog-post";

// Pages
import "./map-page";

// Links handler
new LinksHandler([".lang-switcher", ".pagination"]);

// Accordion setup
document.querySelectorAll(".accordion").forEach(
	(accordion) =>
		new Accordion(accordion, {
			openIcon: require("@icons/plus.svg").default,
			closeIcon: require("@icons/minus.svg").default,
		}),
);

// Fancybox setup
Fancybox.bind("[data-fancybox]", {
	Images: {
		protected: true,
	},
});

// Tippy setup
if (!isTouchDevice()) {
	tippy.setDefaultProps({
		theme: "translucent",
		animation: "scale",
		allowHTML: true,
	});
	tippy("[data-tippy-content]");
	tippy("[data-tippy-content-follow]", {
		followCursor: true,
		plugins: [followCursor],
		content: (reference) => reference.getAttribute("data-tippy-content-follow"),
	});
}
