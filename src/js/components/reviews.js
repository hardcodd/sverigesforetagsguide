import Swal from "sweetalert2";
import ajax from "../core/ajax";

(() => {
	const reviewsForm = document.querySelector(".review-form");
	if (!reviewsForm) return;

	function resetForm() {
		reviewsForm.reset();
		reviewsForm.querySelectorAll(".images-upload__remove").forEach((btn) => {
			btn.click();
		});
	}

	reviewsForm.addEventListener("submit", (e) => {
		e.preventDefault();

		const formData = new FormData(reviewsForm);
		ajax.setDefaultHeader("X-CSRFToken", formData.get("csrfmiddlewaretoken"));

		ajax
			.post(reviewsForm.action, formData)
			.then((response) => {
				Swal.fire({
					icon: "success",
					title: gettext("Success"),
					text: response.message,
					showConfirmButton: true,
					confirmButtonText: "OK",
					confirmButtonColor: "#0074c2",
				}).then(() => {
					resetForm();
				});
			})
			.catch((error) => {
				Swal.fire({
					icon: "error",
					title: gettext("Error"),
					text: error.message,
					showConfirmButton: true,
					confirmButtonText: "OK",
					confirmButtonColor: "#0074c2",
				});
			});
	});
})();
