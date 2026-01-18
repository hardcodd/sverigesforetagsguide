import ajax from "../core/ajax";

// Search city in header
(() => {
	document.querySelectorAll(".city-search-form").forEach((form) => {
		const input = form.querySelector(".city-search-form input");
		const list = form.querySelector(".city-search-form__list");

		if (!input || !list) return;

		// Show list on input focus
		input.addEventListener("focus", () => {
			list.classList.add("show");
		});

		// Save default list state
		const defaultList = list.innerHTML;

		// Remove value during focus
		let value = "";
		input.addEventListener("focus", () => {
			value = input.value;
			input.value = "";
		});
		// Hide list on input blur and restore value
		input.addEventListener("blur", () => {
			setTimeout(() => {
				list.classList.remove("show");
				input.value = value;
				list.innerHTML = defaultList;
			}, 200);
		});

		// Ajax request for cities
		input.addEventListener("input", (e) => {
			const value = e.target.value;
			// chick if value is empty
			if (!value) return (list.innerHTML = defaultList);
			// check if value is less than 2 characters
			if (value.length < 2) return;

			// check if user finished typing
			setTimeout(() => {
				if (value !== input.value) return;

				// show loading
				list.innerHTML = "<div class='circle-loading'></div>";

				// fetch data
				ajax
					.get(`${form.action}?q=${value}`)
					.then((data) => {
						// order data by title
						// data.sort((a, b) => a.title < b.title);

						list.innerHTML = data.length
							? data.map((city) => `<li><a href="${city.url}">${city.title}</a></li>`).join("")
							: `<li>${gettext("No results found")}</li>`;
					})
					.catch(() => {
						list.innerHTML = `<li>${gettext("Error while fetching data")}</li>`;
					});
			}, 500);
		});
	});
})();
