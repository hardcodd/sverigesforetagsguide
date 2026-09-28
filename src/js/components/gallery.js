import ajax from '../core/ajax';

document.addEventListener('DOMContentLoaded', () => {
	const page = document.querySelector('.template-gallery-post-page')
	if (!page) return;

	const container = document.querySelector('.gallery-container');

	const btn = page.querySelector('.btn--load-more');

	btn.addEventListener('click', (e) => {
		e.preventDefault();

		btn.classList.add('loading');

		ajax
			.get(btn.href)
			.then(data => {
				data.forEach((element) => {
					container.insertAdjacentHTML('beforeend', element);
				})
				// Update get parameter 'page' in button href attribute
				const href = new URL(btn.href);
				const totalPages = parseInt(btn.dataset.totalPages)
				let page = parseInt(href.searchParams.get('page'));
				page = page + 1
				if (page > totalPages) {
					btn.remove();
				} else {
					href.searchParams.set('page', page.toString());
					btn.href = href;
				}
		}).finally(() => {
			btn.classList.remove('loading');
		})
	})
});
