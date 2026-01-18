import autosize from "autosize";

export default class Comments {
	constructor() {
		this.commentsForm = $(".comments__form");

		this._formHandler(this.commentsForm);
		this._commentsHandler($(".comments__comment.comment"));
	}

	_formHandler(form) {
		form = $(form);
		if (!form.length) return;

		const textarea = form.find("textarea");
		autosize(textarea);

		form.on("submit", (e) => {
			e.preventDefault();

			const data = this._getFormData(form);

			$.post(form.attr("action"), data)
				.done((newComment) => {
					this._renderNewComment($(newComment));
					this._clearForm(form);
					autosize.update(textarea);
					this._renderCommentsHeader();
					if (form.is(".clone-form")) {
						form.closest(".comment").find(".comment__reply").first().removeAttr("disabled");
					}
				})
				.fail((resp) => {
					alert(resp.responseText);
				});
		});

		// Show/Hide actions
		const actions = form.find(".form__actions");
		actions.hide();
		form.find("textarea").on("focus", () => actions.show());

		// Cancel click
		form.find(".cancel").on("click", (e) => {
			e.preventDefault();
			this._clearForm(form);
			autosize.update(textarea);
		});
	}

	_commentsHandler(comments) {
		comments = $(comments);
		if (!comments.length) return;

		const commentsForm = $(".comments__form");

		comments.each((i) => {
			const comment = $(comments[i]);
			if (!comment.length) return;

			const commentId = comment.attr("id");

			const actions = comment.find(".comment__actions").first();

			// Reply button handler
			actions.find(".comment__reply").on("click", (e) => {
				e.preventDefault();
				e.target.setAttribute("disabled", "disabled");

				const form = commentsForm.clone();
				form.addClass("clone-form");
				form.find("[name=parent_id]").val(commentId.split("-")[1]);

				comment.find(".comment__actions").first().after(form);
				this._formHandler(form);

				form.find("textarea").focus();
			});

			// Delete button handler
			comment
				.find(".comment__delete")
				.first()
				.on("click", (e) => {
					e.preventDefault();

					if (confirm("Delete this comment?")) {
						$.ajax(e.currentTarget.href)
							.done((resp) => {
								this._replaceComment(comment, resp);
								this._renderCommentsHeader();
							})
							.fail((resp) => {
								alert("ERROR: " + resp);
							});
					}
				});

			// Like/Dislike handler
			const reactionButtons = comment.find(".comment__reactions").first();
			reactionButtons.find("a").each((i, a) => {
				$(a).on("click", (e) => {
					e.preventDefault();

					$.ajax(e.currentTarget.href)
						.done((resp) => {
							reactionButtons.find(".comment__reactions_count").first().html(`${resp["likes"]}`);
							reactionButtons.find(".comment__reactions_count").last().html(`${resp["dislikes"]}`);
						})
						.fail(() => {
							alert("Error!");
						});
				});
			});
		});
	}

	_getFormData(form) {
		return {
			csrfmiddlewaretoken: form.find("[name=csrfmiddlewaretoken]").val(),
			content_type: form.find("[name=content_type]").val(),
			object_id: form.find("[name=object_id]").val(),
			parent_id: form.find("[name=parent_id]").val(),
			next: form.find("[name=next]").val(),
			comment: form.find("[name=comment]").val(),
		};
	}

	_renderNewComment(newComment) {
		this.commentsList = $(".comments__list").first();
		if (!this.commentsList) return;
		newComment = $(newComment);

		const parentId = newComment.data("parent") ? `#${newComment.data("parent")}` : undefined;

		if (!parentId) {
			this.commentsList.prepend(newComment);
			return this._commentsHandler(newComment);
		}

		if (!$(parentId).find(".comments__list--children").length) {
			$(parentId).append($('<ul class="comments__list--children"></ul>'));
		}

		$(parentId).find(".comments__list--children").first().prepend(newComment);

		this._commentsHandler(newComment);
	}

	_replaceComment(oldComment, newComment) {
		oldComment = $(oldComment);
		newComment = $(newComment);

		oldComment.replaceWith(newComment);
	}

	_clearForm(form) {
		form = $(form);
		if (!form.length) return;

		const actions = form.find(".form__actions");
		actions.hide();

		if (form.is(".clone-form")) {
			form.closest(".comment").find(".comment__reply").first().removeAttr("disabled");
			return form.remove();
		}

		form.find("[name=parent_id]").val("");
		form.find("[name=comment]").val("");
	}

	_renderCommentsHeader() {
		const form = $(this.commentsForm);
		if (!form.length) return;

		const cType = form.find("[name=content_type]").val();
		const objectId = form.find("[name=object_id]").val();

		const header = $(".comments__header");

		$.get(`/comments/header/?content_type=${cType}&object_id=${objectId}`)
			.done((resp) => {
				header.replaceWith($(resp));
				const count = parseInt($(resp).text().trim());
				$(`[data-comments-count-${objectId}]`).html(`${count}`);
			})
			.fail((resp) => {
				console.error("ERROR: " + resp);
			});
	}
}

document.addEventListener("DOMContentLoaded", () => {
	new Comments();
});
