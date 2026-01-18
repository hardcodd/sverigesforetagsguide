// Check if device is touch device
function isTouchDevice() {
	return "ontouchstart" in window || navigator.maxTouchPoints > 0 || navigator.msMaxTouchPoints > 0;
}

// Function to get color from image
function getColorFromImage(image) {
	const canvas = document.createElement("canvas");
	const ctx = canvas.getContext("2d");

	canvas.width = image.width;
	canvas.height = image.height;

	ctx.drawImage(image, 0, 0, image.width, image.height);

	const data = ctx.getImageData(0, 0, image.width, image.height).data;
	const color = { r: 0, g: 0, b: 0 };

	for (let i = 0; i < data.length; i += 4) {
		color.r += data[i];
		color.g += data[i + 1];
		color.b += data[i + 2];
	}

	const length = data.length / 4;

	color.r = Math.round(color.r / length);
	color.g = Math.round(color.g / length);
	color.b = Math.round(color.b / length);

	return color;
}

// Function to get percentage of color brightness. Min 0.5, Max 1
function getPercentageOfColor(color, min = 0.5, max = 1) {
	const brightness = (color.r * 299 + color.g * 587 + color.b * 114) / 1000;
	const percentage = brightness / 255;
	return Math.min(max, Math.max(min, percentage));
}

// Function to set color to element
function setColorToElement(element, color, minBrightness = 0.5) {
	element.style.setProperty(
		"--highlight-color",
		`rgba(${color.r}, ${color.g}, ${color.b}, ${getPercentageOfColor(color, minBrightness)})`,
	);
}

export { isTouchDevice, getColorFromImage, getPercentageOfColor, setColorToElement };
