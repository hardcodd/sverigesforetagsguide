import { slideToggle } from "../core/dom-slider";

document.addEventListener("DOMContentLoaded", () => {
	const post = document.querySelector(".template-blog-post-page");
	if (!post) return;

	const content = post.querySelector(".blog-post__content");
	if (!content) return;

	const headings = content.querySelectorAll("h2:not(.author__title)");
	if (headings.length === 0) return;

	// Set IDs for headings
	headings.forEach((heading, index) => {
		heading.id = `heading-${index + 1}`;
	});

	// Create Table of Contents
	const toc = document.createElement("nav");
	toc.classList.add("blog-post__toc");

	const tocTitle = document.createElement("h2");
	tocTitle.classList.add("blog-post__toc-title");
	tocTitle.textContent = gettext("Table of Contents");

	// Add svg burger icon to tocTitle
	const svgNS = "http://www.w3.org/2000/svg";
	const burgerIcon = document.createElementNS(svgNS, "svg");
	burgerIcon.setAttribute("width", "16");
	burgerIcon.setAttribute("height", "16");
	burgerIcon.setAttribute("viewBox", "0 0 16 16");
	burgerIcon.setAttribute("fill", "none");
	burgerIcon.innerHTML = `
		<rect y="2" width="16" height="2" fill="currentColor"/>
		<rect y="7" width="16" height="2" fill="currentColor"/>
		<rect y="12" width="16" height="2" fill="currentColor"/>
	`;
	tocTitle.prepend(burgerIcon);
	toc.appendChild(tocTitle);

	const tocList = document.createElement("ul");
	tocList.style.display = "none";

	headings.forEach((heading) => {
		const listItem = document.createElement("li");
		const link = document.createElement("a");
		link.href = `#${heading.id}`;
		link.textContent = heading.textContent;
		listItem.appendChild(link);
		tocList.appendChild(listItem);
	});
	toc.appendChild(tocList);

	// Insert TOC before the first element in the content
	content.insertBefore(toc, content.firstChild);

	// Toggle TOC visibility on title click
	tocTitle.addEventListener("click", () => {
		slideToggle(tocList);
		tocTitle.classList.toggle("active");
	});
});
