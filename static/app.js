async function loadPage(page) {
	try {
		// Обновляем активный пункт меню
		document.querySelectorAll('.nav-item').forEach(item => {
			item.classList.remove('active');
		});

		const activeItem = document.querySelector(`[data-page="${page}"]`);
		if (activeItem) {
			activeItem.classList.add('active');
		}

		const container = document.querySelector('.container');
		const response = await fetch(`/api/page/${page}`);

		if (!response.ok) {
			throw new Error(`Ошибка сервера: ${response.status}`);
		}

		const data = await response.json();

		if (container) {
			container.innerHTML = data.html;


			history.pushState({ page: page }, '', `/${page}`);
		}
	} catch (err) {
		console.error('Ошибка при загрузке страницы:', err);
		const container = document.querySelector('.container');
		if (container) {
			container.innerHTML = `<p class="error">Ошибка загрузки содержимого: ${err.message}</p>`;
		}
	}
}

// Обработка кнопок "Назад/Вперед" в браузере
window.addEventListener('popstate', function (event) {
	const path = window.location.pathname.substring(1) || 'accounts';
	loadPage(path);
});

// Загрузка начальной страницы при первом запуске
document.addEventListener('DOMContentLoaded', function () {
	const currentPage = window.location.pathname.substring(1) || 'accounts';
	// Обновляем активный пункт меню
	document.querySelectorAll('.nav-item').forEach(item => {
		item.classList.remove('active');
	});
	const activeItem = document.querySelector(`[data-page="${currentPage}"]`);
	if (activeItem) {
		activeItem.classList.add('active');
	}
});
