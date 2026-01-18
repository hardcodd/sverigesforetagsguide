import ajax from "./core/ajax";
import { MarkerClusterer } from "@googlemaps/markerclusterer";

window.initMap = function () {
	const mapContainer = document.getElementById("organizations-map");
	if (!mapContainer) return;

	const orgTypeId = mapContainer.dataset.orgTypeId;
	const ll = mapContainer.dataset.ll;
	if (!orgTypeId || !ll) return;

	const fetchUrl = mapContainer.dataset.url;

	const sidebar = document.querySelector(".map-page__sidebar");

	const CITY = {
		lat: parseFloat(ll.split(",")[0]),
		lng: parseFloat(ll.split(",")[1]),
	};

	const map = new google.maps.Map(mapContainer, {
		zoom: 14,
		center: CITY,
		mapId: "the-organizations-map",
	});

	fetchOrganizations(map, fetchUrl, orgTypeId, sidebar);
};

async function fetchOrganizations(map, fetchUrl, orgTypeId, sidebar) {
	try {
		const response = await ajax.get(`${fetchUrl}?org_type_id=${orgTypeId}`);

		const organizations = Object.entries(response).map(([id, org]) => ({
			id,
			title: org.title,
			url: org.url,
			ll: org.ll,
			image: org.image,
			rating: parseFloat(org.rating || 0),
		}));

		let markers = [];
		let clusterer = null;
		let visibleOrgs = [];

		function updateClustersAndSidebar() {
			const bounds = map.getBounds();
			if (!bounds) return;

			// Удаляем старые кластеры
			if (clusterer) clusterer.clearMarkers();

			// Фильтруем организации во вьюпорте
			const visibleMarkers = [];
			visibleOrgs = organizations
				.filter((org) => {
					if (!org.ll) return false;
					const [lat, lng] = org.ll.split(",").map(Number);
					if (isNaN(lat) || isNaN(lng)) return false;

					const position = new google.maps.LatLng(lat, lng);
					if (!bounds.contains(position)) return false;

					const marker = new google.maps.Marker({
						position,
						title: org.title || "",
					});

					marker.addListener("click", () => window.open(org.url, "_blank"));

					visibleMarkers.push(marker);
					return true;
				})
				.sort((a, b) => b.rating - a.rating); // сортировка по рейтингу

			markers = visibleMarkers;

			clusterer = new MarkerClusterer({ map, markers, averageCenter: true, zoomOnClick: true, minimumClusterSize: 2 });

			renderSidebar(visibleOrgs, sidebar);
		}

		// Отложенное обновление при движении карты
		let updateTimeout;
		function scheduleUpdate() {
			clearTimeout(updateTimeout);
			updateTimeout = setTimeout(updateClustersAndSidebar, 500);
		}

		map.addListener("idle", scheduleUpdate);
		updateClustersAndSidebar();

		// Функция рендера карточек с ленивой подгрузкой
		function renderSidebar(orgs, sidebar) {
			sidebar.innerHTML = "";
			if (!orgs.length) {
				sidebar.innerHTML = `<p class="no-results">No organizations in this area</p>`;
				return;
			}

			const container = document.createElement("div");
			container.className = "sidebar-cards";

			// Пагинация: отображаем максимум 20 карточек за раз
			let start = 0;
			const batchSize = 20;

			function renderBatch() {
				const batch = orgs.slice(start, start + batchSize);
				batch.forEach((org) => {
					const card = document.createElement("div");
					card.className = "org-card";
					card.innerHTML = `
						<a href="${org.url}" target="_blank">
							<img src="${org.image}" alt="${org.title}">
							<div class="org-info">
								<h4 title="${org.title}">${org.title}</h4>
								<p>${require("@icons/star.svg").default} ${org.rating.toFixed(1)}</p>
							</div>
						</a>
					`;
					container.appendChild(card);
				});
				start += batchSize;
			}

			renderBatch();
			sidebar.appendChild(container);

			// Добавляем "бесконечную прокрутку"
			sidebar.onscroll = () => {
				if (sidebar.scrollTop + sidebar.clientHeight >= sidebar.scrollHeight - 50) {
					if (start < orgs.length) {
						renderBatch();
					}
				}
			};
		}
	} catch (e) {
		console.error("Error fetching organizations:", e);
	}
}
