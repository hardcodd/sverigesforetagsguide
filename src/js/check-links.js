// Find 404 links on a Page
export default class LinksChecker {
	constructor() {
		this.links = this.getLinks();
		this.countChecked = 0;
		this.count200 = 0;
		this.count404 = 0;
		this.count500 = 0;
		this.links404 = "";
		this.links500 = "";
		this.wasRunning = false;
		this.init();
	}

	init() {
		$(".check-links-btn").click(this.check.bind(this));
		$(".check-links-btn").click(function () {
			$(this).remove();
		});
	}

	getLinks() {
		return $('a[href^="/"]').filter((_, link) => {
			return (
				!link.classList.contains("pagination__link") &&
				link.getAttribute("href") !== "#" &&
				!link.href.includes("ajax_blocks") &&
				!link.href.includes("/admin/")
			);
		});
	}

	render() {
		$(".check-links-result").remove();
		$("body").append(`
			<table class="check-links-result">
				<thead>
					<tr>
						<th>Checked</th>
						<th>${this.countChecked} / ${this.links.length}</th>
					</tr>
				</thead>
				<thead><tr><th>Status</th><th>Count</th></tr></thead>
				<tbody>
					<tr>
						<td>200</td>
						<td>${this.count200}</td>
					</tr>
					<tr>
						<td>404</td>
						<td>${this.count404}</td>
					</tr>
					<tr>
						<td>500</td>
						<td>${this.count500}</td>
					</tr>
				</tbody>
				<thead>
					<tr>
						<th colspan="2">404 Links</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td colspan="2">${this.links404}</td>
					</tr>
				</tbody>
				<thead>
					<tr>
						<th colspan="2">500 Links</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td colspan="2">${this.links500}</td>
					</tr>
				</tbody>
			</table>
		`);
	}

	check() {
		if (this.links.length === 0) return;
		if (this.wasRunning) return;
		this.wasRunning = true;

		this.links.each((_, link) => {
			$.ajax({
				type: "GET",
				url: link.href,
				statusCode: {
					200: () => {
						$(link).addClass("link-status-200").append('<span class="link-status-indicator"></span>');
						this.count200++;
					},
					404: () => {
						$(link).addClass("link-status-404").append('<span class="link-status-indicator"></span>');
						this.count404++;
						this.links404 += `<div><a href="${$(link).attr("href")}">${link.text}</a></div>`;
					},
					500: () => {
						$(link).addClass("link-status-500").append('<span class="link-status-indicator"></span>');
						this.count500++;
						this.links500 += `<div><a href="${$(link).attr("href")}">${link.text}</a></div>`;
					},
				},
				complete: () => {
					this.countChecked++;
					this.render();
				},
			});
		});
	}
}
