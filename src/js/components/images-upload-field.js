class ImagesUploadField {
	constructor(field) {
		this.field = field;
		this.fileInput = field.querySelector("input[type='file']");
		this.files = [];
		this.preview = field.querySelector(".images-upload__preview");
		this.dropArea = field.querySelector(".images-upload__info");
		this.errors = field.querySelector(".images-upload__errors");
		this.maxFileSize = 10 * 1024 * 1024; // 10MB
		this.maxFiles = 10;
		this.init();
	}

	init() {
		this.fileInput.addEventListener("change", (e) => {
			this.handleFiles(e.target.files);
		});

		["dragenter", "dragover"].forEach((event) => {
			this.dropArea.addEventListener(event, (e) => {
				e.preventDefault();
				this.dropArea.classList.add("dragover");
			});
		});

		["dragleave", "drop"].forEach((event) => {
			this.dropArea.addEventListener(event, (e) => {
				e.preventDefault();
				this.dropArea.classList.remove("dragover");
			});
		});

		this.dropArea.addEventListener("drop", (e) => {
			this.handleFiles(e.dataTransfer.files);
		});
	}

	clearErrors() {
		this.errors.innerHTML = "";
	}

	addError(message) {
		for (const error of this.errors.querySelectorAll("p")) {
			if (error.innerText === message) return;
		}

		this.errors.innerHTML += `<p>${message}</p>`;

		this.errors.querySelectorAll("p").forEach((error, i) => {
			setTimeout(
				() => {
					error.style.transition = "all 0.4s";
					error.style.opacity = "0";
					setTimeout(() => {
						error.remove();
					}, 400);
				},
				2000 + i * 400,
			);
		});
	}

	getPreviewTemplate(file) {
		return `
			<div class="images-upload__preview--item">
				<a href="${file}" data-fancybox="images-upload-preview">
					<img src="${file}" class="images-upload__preview--image">
				</a>
				<button class="images-upload__remove" type="button">&times;</button>
			</div>
		`;
	}

	removePreview(file) {
		const previewItem = this.preview.querySelector(`img[src="${file}"]`).closest(".images-upload__preview--item");
		if (previewItem) previewItem.remove();
	}

	addPreview(file) {
		const previewItem = this.getPreviewTemplate(file.dataUrl);
		this.preview.insertAdjacentHTML("beforeend", previewItem);
	}

	removeFile(file) {
		const newFiles = this.files.filter((f) => f.name !== file.name);
		const dataTransfer = new DataTransfer();
		newFiles.forEach((f) => dataTransfer.items.add(f));
		this.fileInput.files = dataTransfer.files;
		this.files = newFiles;
		this.clearErrors();
		this.removePreview(file.dataUrl);
	}

	reduceFileSize(file) {
		return new Promise((resolve) => {
			const img = new Image();
			img.src = URL.createObjectURL(file);

			img.onload = () => {
				const canvas = document.createElement("canvas");
				const ctx = canvas.getContext("2d");

				const maxSize = 800;
				const ratio = Math.min(maxSize / img.width, maxSize / img.height);
				const width = img.width * ratio;
				const height = img.height * ratio;

				canvas.width = width;
				canvas.height = height;

				ctx.drawImage(img, 0, 0, width, height);

				const reducedImageDataUrl = canvas.toDataURL("image/jpeg", 0.8);
				resolve(reducedImageDataUrl);
			};
		});
	}

	reduceFileSize(file) {
		return new Promise((resolve) => {
			const img = new Image();
			img.src = URL.createObjectURL(file);

			img.onload = () => {
				const canvas = document.createElement("canvas");
				const ctx = canvas.getContext("2d");

				const maxSize = 800;
				const ratio = Math.min(maxSize / img.width, maxSize / img.height);
				const width = img.width * ratio;
				const height = img.height * ratio;

				canvas.width = width;
				canvas.height = height;

				ctx.drawImage(img, 0, 0, width, height);

				const reducedImageDataUrl = canvas.toDataURL("image/jpeg", 0.8);
				resolve(reducedImageDataUrl);
			};
		});
	}

	dataURLtoFile(dataurl, filename) {
		const arr = dataurl.split(",");
		const mime = arr[0].match(/:(.*?);/)[1];
		const bstr = atob(arr[1]);
		let n = bstr.length;
		const u8arr = new Uint8Array(n);
		while (n--) {
			u8arr[n] = bstr.charCodeAt(n);
		}
		return new File([u8arr], filename, { type: mime });
	}

	addFile(file) {
		this.files.push(file);
		const dataTransfer = new DataTransfer();
		this.files.forEach((f) => dataTransfer.items.add(this.dataURLtoFile(f.dataUrl, f.name)));
		this.fileInput.files = dataTransfer.files;

		this.addPreview(file);

		const removeButton = this.preview.querySelector(".images-upload__preview--item:last-child .images-upload__remove");
		removeButton.addEventListener("click", () => this.removeFile(file));
	}

	checkUniqueFileName(file) {
		if (this.files.some((f) => f.name === file.name)) {
			this.addError(`${file.name} ${gettext("is already uploaded.")}`);
			return false;
		}
		return true;
	}

	checkFielsCount() {
		if (this.files.length >= this.maxFiles) {
			this.addError(gettext("You can upload a maximum of 10 images."));
			return false;
		}
		return true;
	}

	checkFileSize(file) {
		if (file.size > this.maxFileSize) {
			this.addError(`${file.name} ${gettext("is too large. Max size is 10MB.")}`);
			return false;
		}
		return true;
	}

	checkFileType(file) {
		if (!file.type.startsWith("image/")) {
			this.addError(`${file.name} ${gettext("is not an image.")}`);
			return false;
		} else if (!["image/jpeg"].includes(file.type)) {
			this.addError(`${file.name} ${gettext("is not a valid image type.")}`);
			return false;
		}
		return true;
	}

	checkFile(file) {
		if (!this.checkFielsCount()) return false;
		if (!this.checkUniqueFileName(file)) return false;
		if (!this.checkFileType(file)) return false;
		if (!this.checkFileSize(file)) return false;
		return true;
	}

	handleFiles(files) {
		this.clearErrors();

		[...files].forEach((file) => {
			this.reduceFileSize(file).then((reducedFile) => {
				if (!this.checkFile(file)) return;

				file.dataUrl = reducedFile;
				this.addFile(file);
			});
		});
	}
}

document.querySelectorAll(".images-upload").forEach((field) => new ImagesUploadField(field));
