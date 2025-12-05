let currentFolder = 'all';
let currentSpamFilter = null;
let accounts = [];
let selectedAccounts = new Set();
let avatarLoadingQueue = new Set(); // Очередь на загрузку аватарок
let currentSort = { field: null, direction: 'asc' };
let searchFilter = '';
let roleFilter = '';
let geoFilter = '';
let restFilter = '';
let statusFilter = '';
let activeFilter = null;

function showAddAccountForm() {
	fetch('/api/open-folder?path=Аккаунты')
		.then(response => {
			if (!response.ok) {
				return response.text().then(errorMessage => {
					if (typeof showNotification === 'function') {
						showNotification('Ошибка открытия папки: ' + errorMessage, 'error');
					} else {
						alert('Ошибка открытия папки: ' + errorMessage);
					}
					throw new Error(
						errorMessage ||
							`Ошибка сервера: ${response.status} ${response.statusText}`
					);
				});
			}
			if (typeof showNotification === 'function') {
				showNotification('Папка открыта. Добавьте файлы .session и .json, затем обновите страницу', 'info', 5000);
			}
			// Автоматически обновляем счетчик через 2 секунды после открытия папки
			setTimeout(() => {
				updateAccountCounters();
				loadAccounts(currentFolder);
			}, 2000);
			return response.text();
		})
		.catch(error => {
			console.error('Ошибка при открытии папки:', error.message);
			if (typeof showNotification === 'function') {
				showNotification('Ошибка при открытии папки: ' + error.message, 'error');
			} else {
				alert('Ошибка при открытии папки: ' + error.message);
			}
		});
}

function closeAddAccountForm() {
	document.getElementById('add-account-modal').style.display = 'none';
}

function toggleActionMenu() {
	const menu = document.getElementById('action-menu');
	menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

// Закрытие меню при клике вне его
document.addEventListener('click', function (event) {
	const menu = document.getElementById('action-menu');
	const button = document.getElementById('action-menu-button');

	if (
		menu &&
		menu.style.display === 'block' &&
		!menu.contains(event.target) &&
		event.target !== button
	) {
		menu.style.display = 'none';
	}
});

document.addEventListener('DOMContentLoaded', () => {
	// Элементы DOM
	const workingFolderBtn = document.getElementById('working-folder');
	const archiveFolderBtn = document.getElementById('archive-folder');
	const allFolderBtn = document.getElementById('all-folder');
	const addAccountBtn = document.getElementById('add-account-btn');
	const closeModalBtn = document.getElementById('close-modal-btn');
	const selectAllCheckbox = document.getElementById('select-all-checkbox');

	// Добавляем обработчики для фильтров
	const roleFilterSelect = document.getElementById('role-filter');
	const geoFilterSelect = document.getElementById('geo-filter');
	const restFilterSelect = document.getElementById('rest-filter');
	const statusFilterSelect = document.getElementById('status-filter');
	const folderFilterSelect = document.getElementById('folder-filter');

	if (roleFilterSelect) {
		roleFilterSelect.addEventListener('change', function () {
			roleFilter = this.value;
			renderAccountsTable();
		});
	}

	if (geoFilterSelect) {
		geoFilterSelect.addEventListener('change', function () {
			geoFilter = this.value;
			renderAccountsTable();
		});
	}

	if (restFilterSelect) {
		restFilterSelect.addEventListener('change', function () {
			restFilter = this.value;
			renderAccountsTable();
		});
	}

	if (statusFilterSelect) {
		statusFilterSelect.addEventListener('change', function () {
			statusFilter = this.value;
			renderAccountsTable();
		});
	}

	if (folderFilterSelect) {
		folderFilterSelect.addEventListener('change', function () {
			switchFolder(this.value);
		});
	}

	// Добавляем обработчики для сортировки
	document.querySelectorAll('.sortable-header').forEach(header => {
		header.addEventListener('click', function () {
			const sortField = this.dataset.sort;
			if (currentSort.field === sortField) {
				currentSort.direction =
					currentSort.direction === 'asc' ? 'desc' : 'asc';
			} else {
				currentSort.field = sortField;
				currentSort.direction = 'asc';
			}
			updateSortIndicators();
			renderAccountsTable();
		});
	});

	// Инициализация
	loadAccounts(currentFolder);
	updateAccountCounters();

	// Обработчики событий
	workingFolderBtn?.addEventListener('click', () => switchFolder('working'));
	archiveFolderBtn?.addEventListener('click', () => switchFolder('archive'));
	document.getElementById('no-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('no-spam');
	});
	document.getElementById('with-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('with-spam');
	});
	allFolderBtn?.addEventListener('click', () => switchFolder('all'));
	addAccountBtn?.addEventListener('click', showAddAccountForm);
	closeModalBtn?.addEventListener('click', closeAddAccountForm);

	// Обработчик для чекбокса "Выбрать все"
	selectAllCheckbox?.addEventListener('change', function () {
		if (this.checked) {
			selectAllAccounts();
		} else {
			deselectAllAccounts();
		}
	});

	// Обработчики кнопок управления
	document
		.querySelector('.delete-selected')
		?.addEventListener('click', deleteSelectedAccounts);
	document.querySelector('.select-all')?.addEventListener('click', () => {
		document.getElementById('select-all-checkbox').checked = true;
		selectAllAccounts();
	});
	document.querySelector('.deselect-all')?.addEventListener('click', () => {
		document.getElementById('select-all-checkbox').checked = false;
		deselectAllAccounts();
	});

	document
		.getElementById('action-menu-button')
		?.addEventListener('click', toggleActionMenu);
});

function updateSortIndicators() {
	document.querySelectorAll('.sortable-header').forEach(header => {
		header.classList.remove('sort-asc', 'sort-desc');
		if (header.dataset.sort === currentSort.field) {
			header.classList.add(
				currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc'
			);
		}
	});
}

function switchFolder(folder) {
	currentFolder = folder;
	currentSpamFilter = null;
	updateButtons();
	loadAccounts(folder);

	// Обновляем селект папки
	const folderFilterSelect = document.getElementById('folder-filter');
	if (folderFilterSelect) {
		folderFilterSelect.value = folder;
	}
}

function toggleSpamFilter(filter) {
	currentSpamFilter = currentSpamFilter === filter ? null : filter;
	updateButtons();
	loadAccounts(currentFolder);
}

function updateButtons() {
	// Обновляем активное состояние кнопок папок
	document.querySelectorAll('.account-folder-btn').forEach(btn => {
		btn.classList.remove('active');
	});
	document.getElementById(`${currentFolder}-folder`)?.classList.add('active');

	// Обновляем активное состояние кнопок спама
	if (currentSpamFilter) {
		document
			.getElementById(`${currentSpamFilter}-folder`)
			?.classList.add('active');
	}
}

document.addEventListener('keydown', function (event) {
	if (event.ctrlKey && event.key === 'a') {
		event.preventDefault();
		selectAllAccounts(); // Этот вызов уже обновит UI
	}
});

async function loadAccounts(folder) {
	try {
		const response = await fetch('/get_accounts', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ folder }),
		});

		if (!response.ok) throw new Error('Ошибка загрузки аккаунтов');

		accounts = await response.json();

		// Проверяем, нужно ли загружать аватарки
		checkAndLoadAvatars();

		// Обновляем фильтры
		updateFilterOptions();

		renderAccountsTable();
		updateAccountCounters();
		// Сбросим выделение после загрузки новых данных
		selectedAccounts.clear();
		updateSelectionUI(); // Обновим UI после сброса
		updateSelectionActions();
	} catch (error) {
		console.error('Ошибка загрузки аккаунтов:', error);
	}
}

// Функция для обновления опций фильтров
function updateFilterOptions() {
	const roleDropdown = document.getElementById('role-dropdown');
	const geoDropdown = document.getElementById('geo-dropdown');

	if (roleDropdown) {
		// Собираем уникальные роли
		const roles = [
			...new Set(accounts.map(acc => acc.role).filter(role => role)),
		];
		let options = '<div class="filter-option" data-value="">Все роли</div>';
		roles.forEach(role => {
			options += `<div class="filter-option" data-value="${role}">${role}</div>`;
		});
		roleDropdown.innerHTML = options;
	}

	if (geoDropdown) {
		// Собираем уникальные страны
		const geos = [...new Set(accounts.map(acc => acc.geo).filter(geo => geo))];
		let options = '<div class="filter-option" data-value="">Все страны</div>';
		geos.forEach(geo => {
			options += `<div class="filter-option" data-value="${geo}">${geo}</div>`;
		});
		geoDropdown.innerHTML = options;
	}

	// Добавляем обработчики событий для опций
	document.querySelectorAll('.filter-option').forEach(option => {
		option.addEventListener('click', function (e) {
			e.stopPropagation();
			const filterItem = this.closest('.filter-item');
			const filterType = filterItem
				.querySelector('.filter-dropdown')
				.id.replace('-dropdown', '');
			applyFilter(filterType, this.dataset.value);
		});
	});
}
// Функция для проверки и запуска загрузки аватарок
async function checkAndLoadAvatars() {
	const accountsWithoutAvatars = accounts.filter(account => {
		// Проверяем, есть ли аватарка в session_data
		const avatarUrl = getAvatarFromSession(account.session_data);
		return (
			!avatarUrl &&
			account.status === 'alive' &&
			!avatarLoadingQueue.has(account.id)
		);
	});

	if (accountsWithoutAvatars.length > 0) {
		console.log(
			`Найдено ${accountsWithoutAvatars.length} аккаунтов без аватарок, запускаем загрузку...`
		);

		// Добавляем в очередь на загрузку
		accountsWithoutAvatars.forEach(account => {
			avatarLoadingQueue.add(account.id);
		});

		// Запускаем загрузку аватарок
		await loadAvatarsForAccounts(accountsWithoutAvatars);
	}
}

function getAllProxies() {
	try {
		const proxiesJson = localStorage.getItem('proxies');
		return proxiesJson ? JSON.parse(proxiesJson) : [];
	} catch (e) {
		console.error('Error reading proxies from localStorage:', e);
		return [];
	}
}

// Функция для загрузки аватарок для указанных аккаунтов
async function loadAvatarsForAccounts(accountsToLoad) {
	if (accountsToLoad.length === 0) return;

	try {
		// Получаем прокси через функцию getAllProxies
		const proxies = getAllProxies();

		// const response = await fetch('/load_account_avatars', {
		// 	method: 'POST',
		// 	headers: { 'Content-Type': 'application/json' },
		// 	body: JSON.stringify({
		// 		account_ids: accountsToLoad.map(acc => acc.id),
		// 		current_folder: currentFolder,
		// 		proxies: proxies, // Передаем прокси в запросе
		// 	}),
		// });

		if (!response.ok) {
			throw new Error('Ошибка загрузки аватарок');
		}

		const result = await response.json();
		console.log('Аватарки успешно загружены:', result);

		// Убираем из очереди загрузки
		accountsToLoad.forEach(account => {
			avatarLoadingQueue.delete(account.id);
		});

		// Перезагружаем данные аккаунтов
		// await loadAccounts(currentFolder);
	} catch (error) {
		console.error('Ошибка при загрузке аватарок:', error);
		// Убираем из очереди даже в случае ошибки
		accountsToLoad.forEach(account => {
			avatarLoadingQueue.delete(account.id);
		});
	}
}

// Функция для извлечения аватарки из JSON сессии
function getAvatarFromSession(sessionData) {
	try {
		// Если sessionData уже объект
		if (typeof sessionData === 'object' && sessionData !== null) {
			if (sessionData.img) {
				return sessionData.img;
			}
			// Проверяем другие возможные поля с аватаркой
			if (sessionData.photo) {
				return sessionData.photo;
			}
			if (sessionData.avatar) {
				return sessionData.avatar;
			}
		}
		// Если sessionData строка JSON
		else if (typeof sessionData === 'string') {
			const parsed = JSON.parse(sessionData);
			if (parsed.img) {
				return parsed.img;
			}
			if (parsed.photo) {
				return parsed.photo;
			}
			if (parsed.avatar) {
				return parsed.avatar;
			}
		}
	} catch (e) {
		console.error('Ошибка при парсинге session ', e);
	}
	return null;
}

function applyFiltersAndSort(accounts) {
	let filteredAccounts = accounts;

	// Применяем фильтр по папке и спаму
	filteredAccounts = filteredAccounts.filter(account => {
		let folderMatch = false;
		const status = account.status;

		switch (currentFolder) {
			case 'working':
				folderMatch = status === 'alive';
				break;
			case 'archive':
				folderMatch = status === 'dead';
				break;
			default:
				folderMatch = true;
		}

		let spamMatch = true;
		if (currentSpamFilter === 'no-spam') {
			spamMatch = status !== 'spam_block';
		} else if (currentSpamFilter === 'with-spam') {
			spamMatch = status === 'spam_block';
		}

		return folderMatch && spamMatch;
	});

	// Применяем фильтр по роли
	if (roleFilter) {
		filteredAccounts = filteredAccounts.filter(
			account => account.role === roleFilter
		);
	}

	// Применяем фильтр по гео
	if (geoFilter) {
		filteredAccounts = filteredAccounts.filter(
			account => account.geo === geoFilter
		);
	}

	// Применяем фильтр по отлежке
	if (restFilter) {
		if (restFilter === 'with-rest') {
			filteredAccounts = filteredAccounts.filter(account => account.rest_until);
		} else if (restFilter === 'without-rest') {
			filteredAccounts = filteredAccounts.filter(
				account => !account.rest_until
			);
		}
	}

	// Применяем фильтр по статусу
	if (statusFilter) {
		filteredAccounts = filteredAccounts.filter(
			account => account.status === statusFilter
		);
	}

	// Применяем сортировку
	if (currentSort.field) {
		filteredAccounts.sort((a, b) => {
			let aValue, bValue;

			switch (currentSort.field) {
				case 'index':
					return currentSort.direction === 'asc'
						? a.index - b.index
						: b.index - a.index;
				case 'phone':
					aValue = a.phone || '';
					bValue = b.phone || '';
					break;
				case 'geo':
					aValue = a.geo || '';
					bValue = b.geo || '';
					break;
				case 'status':
					aValue = getStatusText(a.status);
					bValue = getStatusText(b.status);
					break;
				case 'rest':
					aValue = a.rest_until || '';
					bValue = b.rest_until || '';
					break;
				case 'role':
					aValue = a.role || '';
					bValue = b.role || '';
					break;
				case 'used':
					aValue = a.last_used || '';
					bValue = b.last_used || '';
					break;
				case 'name':
					aValue = `${a.first_name || ''} ${a.last_name || ''}`.trim();
					bValue = `${b.first_name || ''} ${b.last_name || ''}`.trim();
					break;
				default:
					return 0;
			}

			if (aValue < bValue) return currentSort.direction === 'asc' ? -1 : 1;
			if (aValue > bValue) return currentSort.direction === 'asc' ? 1 : -1;
			return 0;
		});
	}

	return filteredAccounts;
}

function renderAccountsTable() {
	const tbody = document.querySelector('#accounts-table tbody');
	if (!tbody) return;

	// Применяем фильтры и сортировку
	const finalFilteredAccounts = applyFiltersAndSort(accounts);

	tbody.innerHTML = finalFilteredAccounts
		.map((account, index) => {
			// Форматирование даты отлежки
			let restPeriodText = account.rest_until;

			// Форматирование даты использования
			let usedText = account.last_used;

			// Полное имя
			const fullName = `${account.first_name || ''} ${
				account.last_name || ''
			}`.trim();

			// Получаем аватарку из session_data
			let avatarUrl = null;
			if (account.session_data) {
				avatarUrl = getAvatarFromSession(account.session_data);
			}

			// Если аватарка не найдена и аккаунт в очереди загрузки, показываем индикатор загрузки
			const isAvatarLoading = avatarLoadingQueue.has(account.id);
			const avatarPlaceholder = account.first_name
				? account.first_name.charAt(0).toUpperCase()
				: account.last_name
				? account.last_name.charAt(0).toUpperCase()
				: '?';

			// Получаем информацию о стране и флаг
			const countryInfo = getCountryInfo(account.geo);
			const flagEmoji = getFlagEmoji(account.geo);

			// --- НЕТ НУЖДЫ добавлять обработчики здесь внутри map ---
			// Это приведет к множественным добавлениям обработчиков.
			// Также updateSelectAllCheckbox и updateSelectionUI вызываются внутри map,
			// что неэффективно. Они должны вызываться один раз после рендеринга.
			// ---

			return `
                <tr data-account-id="${account.id}" class="account-row"> 
                    <td>
                        <input type="checkbox" class="account-checkbox" 
                            data-account-id="${account.id}">
                    </td>
                    <td>${index + 1}</td>
                    <td class="avatar-cell">
                        ${
													isAvatarLoading
														? `<div class="avatar-loading">...</div>`
														: avatarUrl
														? `<img src="${avatarUrl}" class="avatar-image" alt="Avatar" data-full-avatar="${avatarUrl}" onclick="openAvatarModal('${avatarUrl}')" onerror="this.onerror=null;this.parentNode.innerHTML='<div class=\\'avatar-placeholder\\'>${avatarPlaceholder}</div>';">`
														: `<div class="avatar-placeholder">${avatarPlaceholder}</div>`
												}
                    </td>
                    <td>${account.phone || ''}</td>
                    <td>
                        <div class="geo-cell" title="${countryInfo.name}">
                            <span class="country-flag">${flagEmoji}</span>
                            <span class="country-code">${
															account.geo || ''
														}</span>
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${getStatusClass(
													account.status
												)}">
                            ${getStatusText(account.status)}
                        </span>
                    </td>
                    <td class="rest-period" data="${
											account.register_time
										}">${restPeriodText}</td>
                    <td>${account.role || ''}</td>
                    <td>${usedText}</td>
                    <td>${fullName || ''}</td>
					<td class="dt-center">
						<div class="action-icon-wrapper" onclick="openAccountLocation(${
								account.id
							})">
							<a data-right-col-action-type="open-account-location">
								<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" is="raptor-icon" data-lucide="folder" data-bs-toggle="tooltip" data-bs-title="Аккаунты\После рассылки\Остальные" class="lucide action-icon-svg" id="rlrks6ckq3t">
									<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path>
								</svg>
							</a>
							<span class="action-icon-text">Папка</span>
						</div>

						<div class="action-icon-wrapper" onclick="copyUsername(${account.id})">
							<a data-right-col-action-type="copy-username" data-bs-toggle="tooltip" data-tooltip-keep-after-click="1" data-bs-title="@vgaqpICm">
								<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" is="raptor-icon" data-lucide="at-sign" class="lucide action-icon-svg" id="ral1oxe3v1n">
									<circle cx="12" cy="12" r="4"></circle>
									<path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"></path>
								</svg>
							</a>
							<span class="action-icon-text">Копировать</span>
						</div>

						<div class="action-icon-wrapper" data-right-col-action-type="show-account-info" onclick="showAccountInfo(${
								account.id
							})">
							<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" is="raptor-icon" data-lucide="info" class="account-extra-info-icon lucide action-icon-svg" id="ri6v1w741p">
								<circle cx="12" cy="12" r="10"></circle>
								<path d="M12 16v-4"></path>
								<path d="M12 8h.01"></path>
							</svg>
							<span class="action-icon-text">Инфо</span>
						</div>

						<div class="action-icon-wrapper" onclick="openAccountInWeb(${account.id})">
							<a data-right-col-action-type="open-dialogs">
								<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary lucide action-icon-svg" is="raptor-icon" data-lucide="screen-share" data-bs-toggle="tooltip" data-bs-title="Открыть аккаунт в вебе" id="rh964pxikht">
									<path d="M13 3H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-3"></path>
									<path d="M8 21h8"></path>
									<path d="M12 17v4"></path>
									<path d="m17 8 5-5"></path>
									<path d="M17 3h5v5"></path>
								</svg>
							</a>
							<span class="action-icon-text">Открыть</span>
						</div>
					</td>
                </tr>
            `;
		})
		.join('');
	
	if (finalFilteredAccounts.length === 0) {
				// Создаем временный элемент для хранения сообщения
				const tempContainer = document.createElement('tr');
				tempContainer.id = 'empty-message-container';
				tempContainer.className = 'empty-message-row';
				tempContainer.style.display = 'table-row';
				tempContainer.innerHTML = `<td colspan="11"> <!-- colspan должен соответствовать количеству столбцов в таблице -->
                    <div class="empty-message-content">
                        <p>Нет аккаунтов</p>
                        <span class="add-account-text" onclick="showAddAccountForm()">Добавить</span>
                    </div>
                </td>`;
				// Вставляем его в tbody
				tbody.appendChild(tempContainer);
			}

	// --- Добавляем обработчики после рендеринга всего tbody ---

	// Добавляем обработчики для чекбоксов
	document.querySelectorAll('.account-checkbox').forEach(checkbox => {
		checkbox.addEventListener('change', function (e) {
			// Останавливаем всплытие, чтобы не сработал клик на строку
			e.stopPropagation();

			const accountId = this.dataset.accountId;
			if (this.checked) {
				selectedAccounts.add(accountId);
			} else {
				selectedAccounts.delete(accountId);
			}
			updateSelectAllCheckbox();
			updateSelectionUI(); // Обновляем UI после изменения выделения
		});
	});

	// Добавляем обработчики для кликов по строкам
	let lastClickedRow = null; // Для отслеживания последней кликнутой строки при shift+click
	document
		.querySelectorAll('#accounts-table tbody .account-row')
		.forEach(row => {
			row.addEventListener('click', function (e) {
				// Игнорируем клик, если он был по интерактивному элементу внутри строки
				if (
					e.target.closest('.action-icon, .account-checkbox, .avatar-image')
				) {
					// Для .account-checkbox мы уже остановили всплытие в его обработчике
					// Для .avatar-image (открытие модалки) и .action-icon (действия) клик не должен выделять строку
					return;
				}

				const accountId = this.dataset.accountId;
				const checkbox = this.querySelector('.account-checkbox');
				if (!checkbox) return;

				const isCtrlPressed = e.ctrlKey || e.metaKey; // Поддержка Cmd на Mac
				const isShiftPressed = e.shiftKey;
				const isAlreadySelected = selectedAccounts.has(accountId); // Проверяем, выделен ли аккаунт

				if (isShiftPressed && lastClickedRow) {
					// Логика выделения диапазона с Shift
					const allRows = Array.from(
						document.querySelectorAll('#accounts-table tbody .account-row')
					);
					const currentIndex = allRows.indexOf(this);
					const lastIndex = allRows.indexOf(lastClickedRow);

					if (currentIndex !== -1 && lastIndex !== -1) {
						const startIndex = Math.min(currentIndex, lastIndex);
						const endIndex = Math.max(currentIndex, lastIndex);

						// Выделяем диапазон (добавляя к существующему выделению)
						for (let i = startIndex; i <= endIndex; i++) {
							const rowToSelect = allRows[i];
							const idToSelect = rowToSelect.dataset.accountId;
							const cb = rowToSelect.querySelector('.account-checkbox');
							if (cb && !cb.checked) {
								cb.checked = true;
								selectedAccounts.add(idToSelect);
							}
						}
					}
					// Не меняем lastClickedRow при shift+click
				} else if (isCtrlPressed) {
					// Логика добавления/удаления с Ctrl/Cmd
					checkbox.checked = !checkbox.checked;
					if (checkbox.checked) {
						selectedAccounts.add(accountId);
					} else {
						selectedAccounts.delete(accountId);
					}
					lastClickedRow = this; // Обновляем последнюю кликнутую строку
				} else {
					// Обычный клик
					if (isAlreadySelected && selectedAccounts.size === 1) {
						// Если кликнули по единственной выделенной строке - снимаем выделение
						checkbox.checked = false;
						selectedAccounts.delete(accountId);
					} else if (isAlreadySelected && selectedAccounts.size > 1) {
						// Если кликнули по одной из выделенных строк (когда выделено несколько)
						// Снимаем выделение только с этой строки
						checkbox.checked = false;
						selectedAccounts.delete(accountId);
					} else {
						// В остальных случаях (не выделена или выделена другая) - выделяем только эту строку
						deselectAllAccounts(); // Это также обновит UI
						checkbox.checked = true;
						selectedAccounts.add(accountId);
					}
					lastClickedRow = this; // Обновляем последнюю кликнутую строку
				}

				// Обновляем состояние "Выделить все"
				updateSelectAllCheckbox();
				// Обновляем UI (кнопки действий и т.д.)
				updateSelectionUI();
			});
		});

	// Обновляем состояние "Выделить все" и UI один раз после рендеринга
	updateSelectAllCheckbox();
	updateSelectionUI();
}

// --- Убедитесь, что функция deselectAllAccounts существует и корректна ---
// Если её нет или она не обновляет UI, вот пример:
/*
function deselectAllAccounts() {
    document.querySelectorAll('.account-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    selectedAccounts.clear();
    updateSelectAllCheckbox();
    updateSelectionUI(); // Важно обновлять UI
}
*/
// Функция для открытия модального окна с аватаркой
function openAvatarModal(avatarUrl) {
	// Создаем модальное окно, если его еще нет
	let modal = document.getElementById('avatar-modal');
	if (!modal) {
		modal = document.createElement('div');
		modal.id = 'avatar-modal';
		modal.className = 'avatar-modal';
		modal.innerHTML = `
            <div class="avatar-modal-content">
                <span class="avatar-modal-close" onclick="closeAvatarModal()">&times;</span>
                <img class="avatar-modal-image" src="" alt="Full size avatar">
            </div>
        `;
		document.body.appendChild(modal);

		// Закрытие по клику вне изображения
		modal.addEventListener('click', function (event) {
			if (event.target === modal) {
				closeAvatarModal();
			}
		});
	}

	// Устанавливаем источник изображения
	const img = modal.querySelector('.avatar-modal-image');
	img.src = avatarUrl;

	// Показываем модальное окно
	modal.classList.add('active');

	// Предотвращаем скролл страницы при открытом модальном окне
	document.body.style.overflow = 'hidden';
}

// Функция для закрытия модального окна с аватаркой
function closeAvatarModal() {
	const modal = document.getElementById('avatar-modal');
	if (modal) {
		modal.classList.remove('active');
	}
	// Восстанавливаем скролл страницы
	document.body.style.overflow = '';
}

// Закрытие модального окна по нажатию Escape
document.addEventListener('keydown', function (event) {
	if (event.key === 'Escape') {
		closeAvatarModal();
	}
});


function updateSelectAllCheckbox() {
	const allCheckboxes = document.querySelectorAll('.account-checkbox');
	const selectAllCheckbox = document.getElementById('select-all-checkbox');

	if (
		allCheckboxes.length > 0 &&
		allCheckboxes.length === selectedAccounts.size
	) {
		selectAllCheckbox.checked = true;
		selectAllCheckbox.indeterminate = false;
	} else if (selectedAccounts.size > 0) {
		selectAllCheckbox.checked = false;
		selectAllCheckbox.indeterminate = true;
	} else {
		selectAllCheckbox.checked = false;
		selectAllCheckbox.indeterminate = false;
	}

	updateSelectionUI(); // Добавлен вызов
	updateSelectionActions();
}

function selectAllAccounts() {
	document.querySelectorAll('.account-checkbox').forEach(checkbox => {
		checkbox.checked = true;
		selectedAccounts.add(checkbox.dataset.accountId);
	});
	updateSelectAllCheckbox();
	updateSelectionUI(); // Добавлен вызов
	updateSelectionActions();
}

function deselectAllAccounts() {
	document.querySelectorAll('.account-checkbox').forEach(checkbox => {
		checkbox.checked = false;
	});
	selectedAccounts.clear();
	updateSelectAllCheckbox();
	updateSelectionUI(); // Добавлен вызов
	updateSelectionActions();
}

async function deleteSelectedAccounts() {
	if (selectedAccounts.size === 0) {
		return;
	}

	try {
		const response = await fetch('/delete_accounts', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				account_ids: Array.from(selectedAccounts),
				current_folder: currentFolder,
			}),
		});

		const result = await response.json();
		if (result.reload === true) {
			window.location.reload();
		} else {
			selectedAccounts.clear();
			loadAccounts(currentFolder);
		}
	} catch (error) {
		console.error('Ошибка удаления аккаунтов:', error);
	}
}

async function postSelectedAccounts(url, additionalData = {}) {
	if (selectedAccounts.size === 0) {
		return false;
	}

	const proxies = getAllProxies();
	// Преобразуем ID аккаунтов в телефоны
	const selected = Array.from(selectedAccounts).map(accountId => {
		const account = accounts.find(acc => acc.id === accountId);
		return account ? account.phone : accountId;
	});

	const data = {
		account_ids: selected,
		proxies: proxies,
		current_folder: currentFolder,
		...additionalData,
	};

	try {
		const response = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(data),
		});

		const result = await response.json();
		if (result.reload === true) {
			window.location.reload();
		}

		return true;
	} catch (error) {
		console.error('Ошибка:', error);
		return false;
	}
}

function closeActionMenu() {
	const menu = document.getElementById('action-menu');
	if (menu) menu.style.display = 'none';
}

// Функции для пунктов меню
async function checkAccounts() {
	closeActionMenu();
	const success = await postSelectedAccounts('/check_accounts');
	if (success) {
		loadAccounts(currentFolder);
	}
}

async function openInWeb() {
	closeActionMenu();
	const success = await postSelectedAccounts('/open_in_web');
}

async function checkSpamBlock() {
	closeActionMenu();
	const success = await postSelectedAccounts('/check_spam_block');
	if (success) {
		loadAccounts(currentFolder);
	}
}



function closeFilterOnClickOutside(event) {
	const filterPanel = document.querySelector('.filters-panel');
	if (!filterPanel.contains(event.target)) {
		document.querySelectorAll('.filter-item').forEach(item => {
			item.classList.remove('active');
		});
		activeFilter = null;
	} else {
		// Проверяем, кликнули ли мы на опцию фильтра
		const filterOption = event.target.closest('.filter-option');
		if (filterOption) {
			const filterItem = event.target.closest('.filter-item');
			const filterType = filterItem
				.querySelector('.filter-dropdown')
				.id.replace('-dropdown', '');

			// Убираем активный класс со всех опций
			filterItem.querySelectorAll('.filter-option').forEach(opt => {
				opt.classList.remove('active');
			});

			// Добавляем активный класс к выбранной опции
			filterOption.classList.add('active');

			// Закрываем dropdown
			filterItem.classList.remove('active');
			activeFilter = null;

			// Применяем фильтр
			applyFilter(filterType, filterOption.dataset.value);
		}
	}
}


function applyFilter(filterType, value) {
	switch (filterType) {
		case 'folder':
			// Для фильтра папки переключаем папку
			switchFolder(value === 'all' ? 'all' : value);
			break;
		case 'role':
			roleFilter = value;
			renderAccountsTable();
			break;
		case 'geo':
			geoFilter = value;
			renderAccountsTable();
			break;
		case 'rest':
			restFilter = value;
			renderAccountsTable();
			break;
		case 'status':
			statusFilter = value;
			renderAccountsTable();
			break;
	}
}

function getStatusClass(status) {
	switch (status) {
		case 'alive':
			return 'alive';
		case 'dead':
			return 'dead';
		case 'spam_block':
			return 'spam-block';
		default:
			return 'unknown';
	}
}

function getStatusText(status) {
	switch (status) {
		case 'alive':
			return 'Без ограничений';
		case 'dead':
			return 'Мертв';
		case 'spam_block':
			return 'Спам блок';
		default:
			return 'Неизвестно';
	}
}

// Объект для управления модальными окнами
const ModalManager = {
	open: (modalId, callback) => {
		const modal = document.getElementById(modalId);
		if (!modal) return;

		modal.style.display = 'block';

		// Фокус на первом инпуте
		const input = modal.querySelector('input');
		if (input) input.focus();

		// Обработчик для кнопки подтверждения
		const confirmBtn = modal.querySelector('.confirm-btn');
		if (confirmBtn) {
			confirmBtn.onclick = async () => {
				try {
					await callback();
				} catch (error) {
					console.error('Error:', error);
				}
			};
		}

		// Закрытие по клику вне окна
		modal.onclick = e => {
			if (e.target === modal) ModalManager.close(modalId);
		};
	},

	close: modalId => {
		const modal = document.getElementById(modalId);
		if (modal) modal.style.display = 'none';
	},

	reset: modalId => {
		const modal = document.getElementById(modalId);
		if (modal) {
			modal.querySelectorAll('input').forEach(input => {
				input.value = '';
			});
		}
	},
};

// Функция изменения фото профиля
async function changePhoto() {
	const fileInput = document.getElementById('photo-input');
	if (!fileInput) return;

	ModalManager.open('edit-photo-modal', async () => {
		if (!fileInput.files?.length) {
			throw new Error('Выберите фото');
		}

		const formData = new FormData();
		formData.append(
			'account_ids',
			JSON.stringify(Array.from(selectedAccounts))
		);
		formData.append('photo', fileInput.files[0]);
		formData.append('current_folder', currentFolder);
		formData.append('proxies', JSON.stringify(getAllProxies()));

		const response = await fetch('/change_photo', {
			method: 'POST',
			body: formData,
		});

		ModalManager.close('edit-photo-modal');
		ModalManager.reset('edit-photo-modal');
		loadAccounts(currentFolder);
	});
}

// Функция изменения имени
async function changeFirstName() {
	ModalManager.open('edit-first-name-modal', async () => {
		const firstName = document.getElementById('first-name-input').value.trim();
		if (!firstName) {
			throw new Error('Введите имя');
		}

		const success = await postSelectedAccounts('/change_first_name', {
			first_name: firstName,
		});

		ModalManager.close('edit-first-name-modal');
		ModalManager.reset('edit-first-name-modal');
		loadAccounts(currentFolder);
	});
}

// Функция изменения фамилии
async function changeLastName() {
	ModalManager.open('edit-last-name-modal', async () => {
		const lastName = document.getElementById('last-name-input').value.trim();
		if (!lastName) {
			throw new Error('Введите фамилию');
		}

		const success = await postSelectedAccounts('/change_last_name', {
			last_name: lastName,
		});

		ModalManager.close('edit-last-name-modal');
		ModalManager.reset('edit-last-name-modal');
		loadAccounts(currentFolder);
	});
}

document.addEventListener('DOMContentLoaded', function () {
	const form = document.getElementById('select-range-form');
	if (form) {
		form.addEventListener('submit', function (e) {
			e.preventDefault();
			const lowerInput = document.getElementById(
				'select-accounts-range-lower-input'
			);
			const upperInput = document.getElementById(
				'select-accounts-range-upper-input'
			);

			let lower = parseInt(lowerInput.value, 10);
			let upper = parseInt(upperInput.value, 10);
			const rows = document.querySelectorAll('#accounts-table tbody tr');

			if (
				isNaN(lower) ||
				isNaN(upper) ||
				lower < 1 ||
				upper < lower ||
				upper > rows.length
			) {
				alert('Пожалуйста, введите корректный диапазон.');
				return;
			}

			// Сначала снимаем все выделения
			deselectAllAccounts(); // Этот вызов уже обновит UI

			// Выделяем нужные строки
			for (let i = lower - 1; i < upper; i++) {
				// -1 потому что индексация с 0
				const checkbox = rows[i].querySelector('.account-checkbox'); // Используем класс
				if (checkbox) {
					checkbox.checked = true;
					selectedAccounts.add(checkbox.dataset.accountId);
				}
			}
			updateSelectAllCheckbox();
			updateSelectionUI();
			updateSelectionActions(); // Обновим UI после выделения диапазона

			// Закрываем дропдаун (если используете Bootstrap JS)
			// const dropdown = bootstrap.Dropdown.getInstance(document.querySelector('#select-range-dropdown .dropdown-toggle'));
			// if (dropdown) dropdown.hide();
			// Или если нет BS JS, можно вручную убрать класс 'show' у .dropdown-menu
			// Но BS обычно сам это делает при submit или клике вне.
		});
	}

	// Инициализация начального состояния UI
	updateSelectionUI();
});

// Обработчик изменения файла
document.addEventListener('DOMContentLoaded', function () {
	const photoInput = document.getElementById('photo-input');
	if (photoInput) {
		photoInput.addEventListener('change', function (e) {
			const statusElement = document.getElementById('file-selected-status');
			const confirmBtn = document.querySelector(
				'#edit-photo-modal .confirm-btn'
			);

			if (this.files && this.files[0]) {
				if (statusElement) statusElement.style.display = 'block';
				if (confirmBtn) confirmBtn.disabled = false;
			} else {
				if (statusElement) statusElement.style.display = 'none';
				if (confirmBtn) confirmBtn.disabled = true;
			}
		});
	}
});

// Обработчики для кнопок папок
document.addEventListener('DOMContentLoaded', function () {
	document.querySelectorAll('.account-folder-btn').forEach(btn => {
		btn.addEventListener('click', function () {
			document.querySelectorAll('.account-folder-btn').forEach(b => {
				b.classList.remove('active');
			});
			this.classList.add('active');
		});
	});
});

// Функция для обновления счетчиков
async function updateAccountCounters() {
	try {
		const response = await fetch('/accounts_count');
		const data = await response.json();

		// Обновляем основные счетчики
		const allCountElement = document.querySelector(
			'#all-folder .account-count'
		);
		if (allCountElement) {
			allCountElement.textContent = data.all || 0;
			allCountElement.setAttribute('data-count', data.all || 0);
		}

		const workingCountElement = document.querySelector(
			'#working-folder .account-count'
		);
		if (workingCountElement) {
			workingCountElement.textContent = data.working || 0;
			workingCountElement.setAttribute('data-count', data.working || 0);
		}

		const archiveCountElement = document.querySelector(
			'#archive-folder .account-count'
		);
		if (archiveCountElement) {
			archiveCountElement.textContent = data.archived || 0;
			archiveCountElement.setAttribute('data-count', data.archived || 0);
		}

		const noSpamCountElement = document.querySelector(
			'#no-spam-folder .account-count'
		);
		if (noSpamCountElement) {
			noSpamCountElement.textContent = data.no_spam || 0;
			noSpamCountElement.setAttribute('data-count', data.no_spam || 0);
		}

		const withSpamCountElement = document.querySelector(
			'#with-spam-folder .account-count'
		);
		if (withSpamCountElement) {
			withSpamCountElement.textContent = data.with_spam || 0;
			withSpamCountElement.setAttribute('data-count', data.with_spam || 0);
		}
	} catch (error) {
		console.error('Ошибка при получении данных:', error);
	}
}
document.addEventListener('DOMContentLoaded', function () {
	const elementsWithTitle = document.querySelectorAll('[data-bs-title]');

	elementsWithTitle.forEach(el => {
		// Создаем элемент тултипа
		const tooltip = document.createElement('div');
		tooltip.className = 'custom-tooltip';
		tooltip.textContent = el.getAttribute('data-bs-title');

		// Добавляем тултип внутрь элемента
		el.appendChild(tooltip);

		// Центрируем по горизонтали при наведении
		el.addEventListener('mouseenter', () => {
			const rect = el.getBoundingClientRect();
			const tooltipWidth = tooltip.offsetWidth;
			tooltip.style.left = `${rect.width / 2}px`;
		});
	});
});

function updateSelectionUI() {
	const deselectBtn = document.getElementById('deselect-all-btn');
	const selectRangeDropdown = document.getElementById('select-range-dropdown'); // Контейнер дропдауна
	const hasSelection = selectedAccounts.size > 0;

	// Показываем/скрываем кнопку "Снять выделение"
	if (deselectBtn) {
		deselectBtn.style.display = hasSelection ? 'flex' : 'none';
	}

	// Показываем/скрываем кнопку "Выделить..." (панель диапазона)
	// Она будет видна, если есть аккаунты и нет выделения, или если дропдаун открыт
	// Для простоты, сделаем её видимой, если есть аккаунты
	const totalAccounts = accounts.length; // или filteredAccounts.length если фильтры применены
	if (selectRangeDropdown) {
		// Показываем, если есть аккаунты и либо нет выделения, либо дропдаун активен
		// Более простой вариант: показываем всегда, если есть аккаунты, а кнопка "Снять выделение" будет перекрывать её при необходимости.
		// Но по вашему запросу: панель появляется при нажатии на кнопку выделить.
		// Поэтому логика будет в обработчике клика по кнопке выделить.
		// Здесь просто убедимся, что она не скрыта по умолчанию каким-то другим способом.
		// selectRangeDropdown.style.display = (totalAccounts > 0 && !hasSelection) ? 'flex' : 'none';
		// Но это конфликтует с тем, что дропдаун должен открываться по клику.
		// Лучше управлять видимостью самой кнопки, которая открывает дропдаун.
		// Однако, Bootstrap Dropdown сам управляет открытием.
		// Поэтому мы просто всегда показываем кнопку, если есть аккаунты.
		// А видимость "Снять выделение" будет зависеть от выделения.
		// Упростим: кнопка "Выделить..." видна, если есть аккаунты.
		// Кнопка "Снять выделение" видна, если есть выделение.
		// Они могут быть видны одновременно.
		// selectRangeDropdown.style.display = totalAccounts > 0 ? 'flex' : 'none';
		// Нет, по ТЗ: панель выделения появляется ТОЛЬКО при нажатии на кнопку выделить.
		// Это сложнее, так как дропдаун управляется Bootstrap.
		// Можно попробовать скрывать/показывать саму кнопку, которая открывает дропдаун.
		// Но это нарушает работу Bootstrap.
		// Альтернатива: сделать кастомную логику открытия дропдауна.
		// Или сделать так, чтобы панель (дропдаун) появляется при клике, и внутри неё уже есть кнопка "Выделить".
		// А кнопка "Выделить..." в основном тулбаре всегда видна, но дропдаун внутри неё появляется при клике.
		// И кнопка "Снять выделение" появляется, если есть выделение.
		// Давайте придерживаться этого.
		// Тогда ничего менять в `display` дропдауна не нужно.
		// Нужно только управлять кнопкой "Снять выделение".
		// И, возможно, саму кнопку "Выделить..." скрывать, если нет аккаунтов.
		// selectRangeDropdown.style.display = totalAccounts > 0 ? 'flex' : 'none';
		// Нет, лучше оставить стандартное поведение BS.
		// Просто убедимся, что кнопка "Снять выделение" появляется при выделении.
	}

	// Обновляем счетчик аккаунтов (если он у вас есть)
	updateAccountsCountLabel();
}

function updateAccountsCountLabel() {
	const label = document.getElementById('accounts-count-label');
	if (label) {
		// Получаем все строки таблицы с аккаунтами (кроме заголовка)
		const tableRows = document.querySelectorAll('#accounts-table tbody tr');
		const displayedCount = tableRows.length; // Количество отображаемых аккаунтов
		const totalCount = accounts.length; // Общее количество аккаунтов
		const selectedCount = selectedAccounts.size; // Количество выделенных аккаунтов

		const text = `Показано аккаунтов ${displayedCount}/${totalCount}`;

		label.textContent = text;
		// Находим элементы для обновления
		const selectedCountElement = document.getElementById('selected-count');
		const totalCountElement = document.getElementById('total-count');

		// Обновляем значения
		if (selectedCountElement) {
			selectedCountElement.textContent = selectedCount;
		}
		if (totalCountElement) {
			totalCountElement.textContent = displayedCount;
		}
	}
}


async function openAccountsDirectory() {
	try {
		const response = await fetch('/open_folder_accounts', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
		});

		const result = await response.json();

		if (!response.ok || !result.success) {
			throw new Error(result.error || 'Не удалось открыть папку аккаунтов');
		}

		console.log('Папка аккаунтов открыта успешно');
	} catch (error) {
		console.error('Ошибка при открытии папки аккаунтов:', error);
		// alert('Не удалось открыть папку аккаунтов: ' + error.message);
	}
}


function getCountryData() {
	return {
		US: { name: 'США' },
		RU: { name: 'Россия' },
		UA: { name: 'Украина' },
		BY: { name: 'Беларусь' },
		KZ: { name: 'Казахстан' },
		UZ: { name: 'Узбекистан' },
		KG: { name: 'Киргизия' },
		MD: { name: 'Молдова' },
		AZ: { name: 'Азербайджан' },
		AM: { name: 'Армения' },
		GE: { name: 'Грузия' },
		TJ: { name: 'Таджикистан' },
		TM: { name: 'Туркменистан' },
		DE: { name: 'Германия' },
		FR: { name: 'Франция' },
		GB: { name: 'Великобритания' },
		IT: { name: 'Италия' },
		ES: { name: 'Испания' },
		PL: { name: 'Польша' },
		CZ: { name: 'Чехия' },
		NL: { name: 'Нидерланды' },
		BE: { name: 'Бельгия' },
		SE: { name: 'Швеция' },
		NO: { name: 'Норвегия' },
		FI: { name: 'Финляндия' },
		DK: { name: 'Дания' },
		IE: { name: 'Ирландия' },
		PT: { name: 'Португалия' },
		GR: { name: 'Греция' },
		TR: { name: 'Турция' },
		IL: { name: 'Израиль' },
		SA: { name: 'Саудовская Аравия' },
		AE: { name: 'ОАЭ' },
		QA: { name: 'Катар' },
		KW: { name: 'Кувейт' },
		BH: { name: 'Бахрейн' },
		OM: { name: 'Оман' },
		JO: { name: 'Иордания' },
		LB: { name: 'Ливан' },
		EG: { name: 'Египет' },
		MA: { name: 'Марокко' },
		TN: { name: 'Тунис' },
		DZ: { name: 'Алжир' },
		ZA: { name: 'ЮАР' },
		NG: { name: 'Нигерия' },
		KE: { name: 'Кения' },
		GH: { name: 'Гана' },
		CI: { name: "Кот-д'Ивуар" },
		SN: { name: 'Сенегал' },
		UG: { name: 'Уганда' },
		TZ: { name: 'Танзания' },
		ZM: { name: 'Замбия' },
		ZW: { name: 'Зимбабве' },
		MW: { name: 'Малави' },
		MZ: { name: 'Мозамбик' },
		AO: { name: 'Ангола' },
		CM: { name: 'Камерун' },
		BJ: { name: 'Бенин' },
		BF: { name: 'Буркина-Фасо' },
		NE: { name: 'Нигер' },
		TD: { name: 'Чад' },
		SO: { name: 'Сомали' },
		SD: { name: 'Судан' },
		SS: { name: 'Южный Судан' },
		ER: { name: 'Эритрея' },
		DJ: { name: 'Джибути' },
		ET: { name: 'Эфиопия' },
		KM: { name: 'Коморы' },
		SC: { name: 'Сейшельские острова' },
		MU: { name: 'Маврикий' },
		MG: { name: 'Мадагаскар' },
		RE: { name: 'Реюньон' },
		YT: { name: 'Майотта' },
		CN: { name: 'Китай' },
		JP: { name: 'Япония' },
		KR: { name: 'Южная Корея' },
		KP: { name: 'Северная Корея' },
		VN: { name: 'Вьетнам' },
		TH: { name: 'Таиланд' },
		SG: { name: 'Сингапур' },
		MY: { name: 'Малайзия' },
		ID: { name: 'Индонезия' },
		PH: { name: 'Филиппины' },
		MM: { name: 'Мьянма' },
		KH: { name: 'Камбоджа' },
		LA: { name: 'Лаос' },
		BN: { name: 'Бруней' },
		TL: { name: 'Восточный Тимор' },
		IN: { name: 'Индия' },
		PK: { name: 'Пакистан' },
		BD: { name: 'Бангладеш' },
		LK: { name: 'Шри-Ланка' },
		MV: { name: 'Мальдивы' },
		NP: { name: 'Непал' },
		BT: { name: 'Бутан' },
		AF: { name: 'Афганистан' },
		IR: { name: 'Иран' },
		IQ: { name: 'Ирак' },
		SY: { name: 'Сирия' },
		PS: { name: 'Палестина' },
		YE: { name: 'Йемен' },
		CY: { name: 'Кипр' },
		BG: { name: 'Болгария' },
		RO: { name: 'Румыния' },
		RS: { name: 'Сербия' },
		HR: { name: 'Хорватия' },
		SI: { name: 'Словения' },
		BA: { name: 'Босния и Герцеговина' },
		ME: { name: 'Черногория' },
		MK: { name: 'Северная Македония' },
		AL: { name: 'Албания' },
		XK: { name: 'Косово' },
		MT: { name: 'Мальта' },
		IS: { name: 'Исландия' },
		LU: { name: 'Люксембург' },
		LI: { name: 'Лихтенштейн' },
		AD: { name: 'Андорра' },
		MC: { name: 'Монако' },
		SM: { name: 'Сан-Марино' },
		VA: { name: 'Ватикан' },
		CH: { name: 'Швейцария' },
		AT: { name: 'Австрия' },
		HU: { name: 'Венгрия' },
		SK: { name: 'Словакия' },
		EE: { name: 'Эстония' },
		LV: { name: 'Латвия' },
		LT: { name: 'Литва' },
		CA: { name: 'Канада' },
		MX: { name: 'Мексика' },
		BR: { name: 'Бразилия' },
		AR: { name: 'Аргентина' },
		CL: { name: 'Чили' },
		PE: { name: 'Перу' },
		CO: { name: 'Колумбия' },
		VE: { name: 'Венесуэла' },
		EC: { name: 'Эквадор' },
		BO: { name: 'Боливия' },
		PY: { name: 'Парагвай' },
		UY: { name: 'Уругвай' },
		GY: { name: 'Гайана' },
		SR: { name: 'Суринам' },
		AU: { name: 'Австралия' },
		NZ: { name: 'Новая Зеландия' },
		FJ: { name: 'Фиджи' },
		PG: { name: 'Папуа — Новая Гвинея' },
		SB: { name: 'Соломоновы Острова' },
		VU: { name: 'Вануату' },
	};
}

// Функция для получения информации о стране
function getCountryInfo(countryCode) {
	const countryData = getCountryData();
	return countryData[countryCode] || { name: countryCode || 'Неизвестно' };
}

// Функция для получения emoji флага по коду страны
function getFlagEmoji(countryCode) {
	if (!countryCode) return '🏳️';

	// Преобразуем код страны в emoji флаг
	const codePoints = countryCode
		.toUpperCase()
		.split('')
		.map(char => 127397 + char.charCodeAt(0));

	try {
		return String.fromCodePoint(...codePoints);
	} catch (e) {
		return '🏳️';
	}
}

// Запускаем обновление счетчиков при загрузке и каждые 30 секунд
document.addEventListener('DOMContentLoaded', function () {
	updateAccountCounters();
	setInterval(updateAccountCounters, 30000);
});


// Создаем элемент тултипа один раз
const tooltip = document.createElement('div');
tooltip.id = 'floating-tooltip';
tooltip.style.cssText = `
    position: fixed;
    background-color: #4a4a4a;
    color: #ffffff;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 13px;
    white-space: nowrap;
    z-index: 2147483647;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s ease, visibility 0.2s ease;
    pointer-events: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    /* transform-origin для плавной анимации */
    transform-origin: center bottom;
`;
document.body.appendChild(tooltip);

// Убираем создание элемента стрелочки

let currentTarget = null;

// Обработчики событий для элементов с тултипами
document.addEventListener('mouseover', function(e) {
    // Ищем ближайший родительский элемент с классом 'geo-cell'
    const geoCell = e.target.closest('.geo-cell');
    // Проверяем, есть ли у этого элемента атрибут title
    if (geoCell && geoCell.hasAttribute('title')) {
        const title = geoCell.getAttribute('title');
        if (title) {
            currentTarget = geoCell; // Сохраняем ссылку на .geo-cell
            // Устанавливаем текст тултипа
            tooltip.textContent = title;
            
            // Небольшая задержка для корректного расчета размеров
            requestAnimationFrame(() => {
                // Получаем координаты элемента .geo-cell
                const rect = geoCell.getBoundingClientRect();
                const scrollTop = window.scrollY || document.documentElement.scrollTop;
                const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
                
                // Позиционируем тултип по центру над элементом .geo-cell
                const tooltipTop = rect.top + scrollTop - tooltip.offsetHeight - 8; // 8px отступ
                const tooltipLeft = rect.left + scrollLeft + (rect.width / 2);
                
                tooltip.style.top = `${tooltipTop}px`;
                tooltip.style.left = `${tooltipLeft}px`;
                tooltip.style.transform = 'translateX(-50%)';
                
                // Показываем тултип
                tooltip.style.opacity = '1';
                tooltip.style.visibility = 'visible';
            });
        }
    }
});

document.addEventListener('mouseout', function(e) {
    // Ищем ближайший родительский элемент с классом 'geo-cell'
    const geoCell = e.target.closest('.geo-cell');
    if (geoCell && geoCell.hasAttribute('title')) {
        currentTarget = null;
        // Скрываем тултип
        tooltip.style.opacity = '0';
        tooltip.style.visibility = 'hidden';
    }
});

// Дополнительно: обновляем позицию при прокрутке/ресайзе, если тултип открыт
function updateTooltipPosition() {
    if (currentTarget && tooltip.style.opacity === '1') {
        // Используем currentTarget (это .geo-cell)
        const rect = currentTarget.getBoundingClientRect();
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
        
        const tooltipTop = rect.top + scrollTop - tooltip.offsetHeight - 8;
        const tooltipLeft = rect.left + scrollLeft + (rect.width / 2);
        
        tooltip.style.top = `${tooltipTop}px`;
        tooltip.style.left = `${tooltipLeft}px`;
        tooltip.style.transform = 'translateX(-50%)';
    }
}

// --- Добавить обработчик для тултипа отлежки ---
// Предполагается, что ячейка с отлежкой имеет класс 'rest-period-cell'
// --- Добавить обработчик для тултипа отлежки ---
document.addEventListener('mouseover', function(e) {
    // Ищем ячейку с классом 'rest-period'
    const restCell = e.target.closest('.rest-period');
    
    // Проверяем, есть ли у нее атрибут data
    if (restCell && restCell.hasAttribute('data')) {
        const registerTimestampStr = restCell.getAttribute('data');
        
        // Проверяем, что значение не пустое и является числом
        const registerTimestamp = parseInt(registerTimestampStr, 10);
        if (!isNaN(registerTimestamp) && registerTimestamp > 0) {
            currentTarget = restCell; // Используем существующую переменную

            // Форматируем дату
            const registerDate = new Date(registerTimestamp * 1000); // JS использует миллисекунды
            const day = String(registerDate.getDate()).padStart(2, '0');
            const month = String(registerDate.getMonth() + 1).padStart(2, '0'); // Месяцы с 0
            const year = registerDate.getFullYear();
            const hours = String(registerDate.getHours()).padStart(2, '0');
            const minutes = String(registerDate.getMinutes()).padStart(2, '0');
            
            const formattedDate = `${day}.${month}.${year} ${hours}:${minutes}`;

            // Устанавливаем текст тултипа
            tooltip.textContent = `Зарегистрирован ${formattedDate}`;
            
            // Небольшая задержка для корректного расчета размеров
            requestAnimationFrame(() => {
                // Получаем координаты элемента .rest-period
                const rect = restCell.getBoundingClientRect();
                const scrollTop = window.scrollY || document.documentElement.scrollTop;
                const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
                
                // Позиционируем тултип по центру над элементом
                const tooltipTop = rect.top + scrollTop - tooltip.offsetHeight - 8; // 8px отступ
                const tooltipLeft = rect.left + scrollLeft + (rect.width / 2);
                
                tooltip.style.top = `${tooltipTop}px`;
                tooltip.style.left = `${tooltipLeft}px`;
                tooltip.style.transform = 'translateX(-50%)';
                
                // Показываем тултип
                tooltip.style.opacity = '1';
                tooltip.style.visibility = 'visible';
            });
        }
    }
    // Обработчик для geo-cell остается без изменений
});

document.addEventListener('mouseout', function(e) {
    const restCell = e.target.closest('.rest-period');
    const geoCell = e.target.closest('.geo-cell');
    
    if (restCell || geoCell) {
        currentTarget = null;
        // Скрываем тултип
        tooltip.style.opacity = '0';
        tooltip.style.visibility = 'hidden';
    }
});

function updateSelectionActions() {
	const container = document.getElementById('selection-actions');
	if (selectedAccounts.size > 0) {
		container.style.display = 'flex';
	} else {
		container.style.display = 'none';
	}
}

// --- Добавить обработчик для тултипа иконок действий ---
document.addEventListener('mouseover', function(e) {
    // Ищем ближайший родительский элемент с классом 'action-icon-wrapper'
    const iconWrapper = e.target.closest('.action-icon-wrapper');
    
    // Проверяем, есть ли у него дочерний элемент с классом 'action-icon-text'
    if (iconWrapper) {
        const textElement = iconWrapper.querySelector('.action-icon-text');
        // Проверяем, существует ли текстовый элемент и не пуст ли он
        if (textElement && textElement.textContent.trim()) {
            currentTarget = iconWrapper; // Сохраняем ссылку на .action-icon-wrapper
            
            // Устанавливаем текст тултипа из скрытого span
            tooltip.textContent = textElement.textContent.trim();
            
            // Небольшая задержка для корректного расчета размеров
            requestAnimationFrame(() => {
                // Получаем координаты элемента .action-icon-wrapper
                const rect = iconWrapper.getBoundingClientRect();
                const scrollTop = window.scrollY || document.documentElement.scrollTop;
                const scrollLeft = window.scrollX || document.documentElement.scrollLeft;
                
                // Позиционируем тултип по центру над элементом .action-icon-wrapper
                // Используем те же расчеты, что и в других обработчиках
                const tooltipTop = rect.top + scrollTop - tooltip.offsetHeight - 8; // 8px отступ
                const tooltipLeft = rect.left + scrollLeft + (rect.width / 2);
                
                tooltip.style.top = `${tooltipTop}px`;
                tooltip.style.left = `${tooltipLeft}px`;
                tooltip.style.transform = 'translateX(-50%)';
                
                // Показываем тултип
                tooltip.style.opacity = '1';
                tooltip.style.visibility = 'visible';
            });
        }
    }
    // Обработчики для .geo-cell и .rest-period остаются без изменений
});

document.addEventListener('mouseout', function(e) {
    const iconWrapper = e.target.closest('.action-icon-wrapper');
    const restCell = e.target.closest('.rest-period');
    const geoCell = e.target.closest('.geo-cell');
    
    // Если мы вышли из любого из этих элементов, скрываем тултип
    if (iconWrapper || restCell || geoCell) {
        currentTarget = null;
        // Скрываем тултип
        tooltip.style.opacity = '0';
        tooltip.style.visibility = 'hidden';
    }
});

// Обработчик updateTooltipPosition не требует изменений, 
// так как он уже использует currentTarget.getBoundingClientRect()
// --- Конец добавления обработчика для тултипа отлежки ---
// --- Конец добавления обработчика для тултипа отлежки ---

window.addEventListener('scroll', updateTooltipPosition);
window.addEventListener('resize', updateTooltipPosition);


// --- Новый код для кастомного меню выделения диапазона ---
document.addEventListener('DOMContentLoaded', function () {
    const selectRangeButton = document.getElementById('select-range-button');
    const customMenu = document.getElementById('select-range-custom-menu');
    const form = document.getElementById('select-range-form');

    // Переменная для отслеживания состояния меню
    let isMenuOpen = false;

    if (selectRangeButton && customMenu && form) {
        // Обработчик клика по кнопке
        selectRangeButton.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleCustomMenu(selectRangeButton);
        });

        // Функция переключения кастомного меню
        function toggleCustomMenu(buttonElement) {
            if (isMenuOpen) {
                closeCustomMenu();
            } else {
                openCustomMenu(buttonElement);
            }
        }

        // Функция открытия кастомного меню
        function openCustomMenu(buttonElement) {
            const rect = buttonElement.getBoundingClientRect();

            // Позиционирование под кнопкой
            customMenu.style.top = (rect.bottom) + 'px';
            customMenu.style.left = (rect.left - 300) + 'px';
            customMenu.style.display = 'block';
            
            isMenuOpen = true;

            // Закрытие при клике вне меню
            document.addEventListener('click', handleClickOutside);
        }

        // Функция закрытия кастомного меню
        function closeCustomMenu() {
            customMenu.style.display = 'none';
            isMenuOpen = false;
            document.removeEventListener('click', handleClickOutside);
        }

        // Обработчик клика вне меню
        function handleClickOutside(event) {
            if (!customMenu.contains(event.target) && !selectRangeButton.contains(event.target)) {
                closeCustomMenu();
            }
        }

        // Обработчик отправки формы
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const lowerInput = document.getElementById('select-range-lower-input');
            const upperInput = document.getElementById('select-range-upper-input');

            let lower = parseInt(lowerInput.value, 10);
            let upper = parseInt(upperInput.value, 10);
            const maxIndex = document.querySelectorAll('#accounts-table tbody tr').length;

           if (isNaN(lower) || isNaN(upper) || lower < 1 || upper < 1) {
				// Если введены некорректные значения (не числа или <= 0), просто закрываем меню
				closeSelectRangeModal(); // Или closeCustomMenu(), в зависимости от имени вашей функции
				return;
			}

			if (lower > maxIndex) {
				lower = maxIndex;
				upper = maxIndex;
			}
			// Корректируем upper, если он больше максимального индекса
			if (upper > maxIndex) {
				upper = maxIndex;
			}
            // Снимаем все выделения
            deselectAllAccounts();

            // Выделяем нужные строки
            const rows = document.querySelectorAll('#accounts-table tbody tr');
            for (let i = lower - 1; i < upper; i++) {
                if (i >= 0 && i < rows.length) {
                    const checkbox = rows[i].querySelector('.account-checkbox');
                    if (checkbox) {
                        checkbox.checked = true;
                        selectedAccounts.add(checkbox.dataset.accountId);
                    }
                }
            }

            updateSelectAllCheckbox();
            updateSelectionUI();
            updateSelectionActions();

            // Закрываем меню
            closeCustomMenu();
        });
        
        // Закрытие меню по нажатию Escape
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && isMenuOpen) {
                closeCustomMenu();
            }
        });
    }
});


