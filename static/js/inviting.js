function showAddAccountForm() {
	document.getElementById('add-account-modal').style.display = 'flex';
}

function closeAddAccountForm() {
	document.getElementById('add-account-modal').style.display = 'none';
}

function toggleSettings(id) {
	const element = document.getElementById(id);
	const checkbox = document.querySelector(
		`input[onchange="toggleSettings('${id}')"]`
	);

	if (checkbox.checked) {
		element.style.display = 'block';
	} else {
		element.style.display = 'none';
	}
}

let currentFolder = 'all';
let accounts = [];
let selectedAccounts = new Set();

document.addEventListener('DOMContentLoaded', () => {
	// Элементы DOM

	const workingFolderBtn = document.getElementById('working-folder');
	const archiveFolderBtn = document.getElementById('archive-folder');
	const allFolderBtn = document.getElementById('all-folder');
	const addAccountBtn = document.getElementById('add-account-btn');
	const closeModalBtn = document.getElementById('close-modal-btn');

	// Инициализация
	loadAccounts(currentFolder);

	// Обработчики событий
	workingFolderBtn?.addEventListener('click', () => switchFolder('working'));
	archiveFolderBtn?.addEventListener('click', () => switchFolder('archive'));
	document.getElementById('no-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('no-spam');
		filterAccounts(); // Добавляем вызов фильтрации
		updateAccountCounters();
	});

	document.getElementById('with-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('with-spam');
		filterAccounts(); // Добавляем вызов фильтрации
		updateAccountCounters();
	});
	allFolderBtn?.addEventListener('click', () => switchFolder('all'));
	addAccountBtn?.addEventListener('click', showAddAccountForm);
	closeModalBtn?.addEventListener('click', closeAddAccountForm);

	// Обработчики кнопок управления
	document
		.querySelector('.delete-selected')
		?.addEventListener('click', deleteSelectedAccounts);
	document
		.querySelector('.add-new')
		?.addEventListener('click', showAddAccountForm);
	document
		.querySelector('.select-all')
		?.addEventListener('click', selectAllAccounts);
	document
		.querySelector('.deselect-all')
		?.addEventListener('click', deselectAllAccounts);

	// Функции
	function switchFolder(folder) {
		currentFolder = folder;
		currentSpamFilter = null; // Сбрасываем фильтр спама при смене папки
		updateButtons();
		loadAccounts(folder);
	}

	function toggleSpamFilter(filter) {
		currentSpamFilter = currentSpamFilter === filter ? null : filter;

		updateButtons();
		filterAccounts();
	}

	function updateButtons() {
		// Обновляем активное состояние кнопок папок
		document
			.querySelectorAll('.folder-selector .account-folder-btn')
			.forEach(btn => {
				btn.classList.remove('active');
			});
		document.getElementById(`${currentFolder}-folder`)?.classList.add('active');
	}

	function filterAccounts() {
		const rows = document.querySelectorAll('#accounts-table tbody tr');

		rows.forEach(row => {
			const statusBadge = row.querySelector('.status-badge');
			if (!statusBadge) return;

			const status = statusBadge.classList[1];
			const isWorking = status === 'alive';
			const isArchive = status === 'dead';
			const hasSpam = status === 'spam-block';

			let folderMatch = false;
			switch (currentFolder) {
				case 'working':
					folderMatch = isWorking;
					break;
				case 'archive':
					folderMatch = isArchive;
					break;
				default:
					folderMatch = true;
			}

			let spamMatch = true;
			if (currentSpamFilter === 'no-spam') {
				spamMatch = !hasSpam;
			} else if (currentSpamFilter === 'with-spam') {
				spamMatch = hasSpam;
			}

			// Применяем оба фильтра
			const shouldShow = folderMatch && spamMatch;
			row.style.display = shouldShow ? '' : 'none';
		});

		// Обновляем счетчики после фильтрации
		updateAccountCounters();
	}
	async function loadAccounts(folder) {
		try {
			const response = await fetch('/get_accounts', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ folder }),
			});

			if (!response.ok) throw new Error('Ошибка загрузки аккаунтов');

			accounts = await response.json();
			renderAccountsTable();
		} catch (error) {
			console.error('Ошибка загрузки аккаунтов:', error);
		}
	}
	function updateControls() {
		const controls = document.querySelector('.table-controls');
		const hasSelected = selectedAccounts.size > 0;
		controls?.classList.toggle('has-selected', hasSelected);
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
			menu.style.display === 'block' &&
			!menu.contains(event.target) &&
			event.target !== button
		) {
			menu.style.display = 'none';
		}
	});
	function renderAccountsTable() {
		const tbody = document.querySelector('#accounts-table tbody');
		if (!tbody) return;

		tbody.innerHTML = accounts
			.map(
				(account, index) => `
            <tr>
                <td class="selector-cell">
                    <input type="checkbox" class="selector-checkbox" 
                        ${selectedAccounts.has(index) ? 'checked' : ''}
                        data-index="${index}">
                </td>
                <td>${account.phone || ''}</td>
                <td class="geo-cell">
                    <img src="${account.flag_code || 'default'}.png" alt="${
					account.country || ''
				}" class="country-flag">
                    <span>${account.country || ''}</span>
                </td>
                <td>${account.role || '-'}</td>
                <td>${account.name || '-'}</td>
                <td>
                    <span class="status-badge ${getStatusClass(
											account.status
										)}">
                        ${getStatusText(account.status)}
                    </span>
                </td>
								<td>
					<button class="web-open-button" onclick="openInWebNumber('${
						account.phone || ''
					}')">
						Открыть в web <img src="static/images/web.png" alt="Веб" class="nav-icon">
					</button>
            	</td>
            </tr>
        `
			)
			.join('');

		// Добавляем обработчики для чекбоксов
		document.querySelectorAll('.selector-checkbox').forEach(checkbox => {
			checkbox.addEventListener('change', function () {
				const index = parseInt(this.dataset.index);
				this.checked
					? selectedAccounts.add(index)
					: selectedAccounts.delete(index);
				updateControls(); // Обновляем состояние кнопок
			});
		});

		updateControls(); // Обновляем состояние кнопок после рендеринга таблицы
	}

	function selectAllAccounts() {
		// Если уже все выбраны - снимаем выбор
		if (selectedAccounts.size === accounts.length) {
			deselectAllAccounts();
			return;
		}

		// Иначе выбираем все
		accounts.forEach((_, index) => selectedAccounts.add(index));
		renderAccountsTable();
	}

	function deselectAllAccounts() {
		selectedAccounts.clear();
		renderAccountsTable();
	}

	async function deleteSelectedAccounts() {
		const selected = Array.from(selectedAccounts).map(
			index => accounts[index].phone
		);
		if (selected.length === 0) {
			return;
		}

		try {
			const response = await fetch('/delete_accounts', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					account_ids: selected,
					current_folder: currentFolder,
				}),
			});

			const result = await response.json();
			if (result.reload === true) {
				window.location.reload();
			}
		} catch (error) {
			console.error('Ошибка удаления аккаунтов:', error);
		}
	}
});

function getAllProxies() {
	try {
		const proxiesJson = localStorage.getItem('proxies');
		return proxiesJson ? JSON.parse(proxiesJson) : [];
	} catch (e) {
		console.error('Error reading proxies from localStorage:', e);
		return [];
	}
}

async function postSelectedAccounts(url, additionalData = {}) {
	if (selectedAccounts.size === 0) {
		return false;
	}
	const proxies = getAllProxies();
	const selected = Array.from(selectedAccounts).map(
		index => accounts[index].phone
	);

	const data = {
		account_ids: selected,
		proxies: Array.from(selectedAccounts).map(index => proxies[index]),
		current_folder: currentFolder, // Добавляем текущую папку
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
	} catch (error) {
		return false;
	}
}
function closeActionMenu() {
	document.getElementById('action-menu').style.display = 'none';
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

// Обновление текста предпросмотра
function updateMessagePreview() {
	const text = document.getElementById('message-text').value;
	const previewText = document.getElementById('message-preview-text');
	const photoCaption = document.getElementById('photo-caption');

	previewText.textContent =
		text || 'Введите текст сообщения, чтобы увидеть предпросмотр...';
	photoCaption.textContent = text;
}

// Обновление превью фото
function updatePhotoPreview(file) {
	const previewPhoto = document.getElementById('message-preview-photo');
	const img = document.getElementById('preview-photo-img');

	if (file) {
		const reader = new FileReader();
		reader.onload = function (e) {
			img.src = e.target.result;
			previewPhoto.style.display = 'block';
		};
		reader.readAsDataURL(file);
	} else {
		previewPhoto.style.display = 'none';
	}
}

// Обработчик изменения файла
document
	.getElementById('file-attachment')
	.addEventListener('change', function (e) {
		updatePhotoPreview(e.target.files[0]);
	});

// Инициализация
document.addEventListener('DOMContentLoaded', function () {
	updateMessagePreview();
});

async function openInWebNumber(phoneNumber) {
	const proxies = getAllProxies();
	formData.append('proxies', JSON.stringify(proxies));
	const data = {
		account_ids: Array.of(phoneNumber),
		proxies: JSON.stringify(proxies),
		current_folder: currentFolder, // Добавляем текущую папку
	};

	try {
		const response = await fetch('/open_in_web', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(data),
		});

		const result = await response.json();
		if (result.reload === true) {
			window.location.reload();
		}
	} catch (error) {
		return false;
	}
}

async function checkSpamBlock() {
	closeActionMenu();
	const success = await postSelectedAccounts('/check_spam_block');
	if (success) {
		loadAccounts(currentFolder);
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

// Функция для получения текста статуса
function getStatusText(status) {
	switch (status) {
		case 'alive':
			return 'Живой';
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
	// Открытие модального окна
	open: (modalId, callback) => {
		const modal = document.getElementById(modalId);
		modal.style.display = 'block';

		// Фокус на первом инпуте
		const input = modal.querySelector('input');
		if (input) input.focus();

		// Обработчик для кнопки подтверждения
		modal.querySelector('.confirm-btn').onclick = async () => {
			try {
				await callback();
			} catch (error) {
				console.error('Error:', error);
			}
		};

		// Закрытие по клику вне окна
		modal.onclick = e => {
			if (e.target === modal) ModalManager.close(modalId);
		};
	},

	// Закрытие модального окна
	close: modalId => {
		document.getElementById(modalId).style.display = 'none';
	},

	// Сброс значений формы
	reset: modalId => {
		const modal = document.getElementById(modalId);
		modal.querySelectorAll('input').forEach(input => {
			input.value = '';
		});
	},
};

// Функция изменения фото профиля
async function changePhoto() {
	const fileInput = document.getElementById('photo-input');

	ModalManager.open('edit-photo-modal', async () => {
		if (!fileInput.files?.length) {
			throw new Error('Выберите фото');
		}

		const formData = new FormData();
		const selected = Array.from(selectedAccounts).map(
			index => accounts[index].phone
		);
		const proxies = getAllProxies();

		formData.append('account_ids', JSON.stringify(selected));
		formData.append('photo', fileInput.files[0]);
		formData.append('current_folder', currentFolder);
		formData.append('proxies', JSON.stringify(proxies));

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

document.getElementById('photo-input').addEventListener('change', function (e) {
	const statusElement = document.getElementById('file-selected-status');
	const confirmBtn = document.getElementById('confirm-btn');

	if (this.files && this.files[0]) {
		// Показываем статус
		statusElement.style.display = 'block';
		// Активируем кнопку сохранения
		confirmBtn.disabled = false;
	} else {
		// Скрываем статус
		statusElement.style.display = 'none';
		// Деактивируем кнопку
		confirmBtn.disabled = true;
	}
});

document.querySelectorAll('.account-folder-btn').forEach(btn => {
	btn.addEventListener('click', function () {
		// Удаляем active у всех кнопок
		document.querySelectorAll('.account-folder-btn').forEach(b => {
			b.classList.remove('active');
		});

		// Добавляем active к текущей кнопке
		this.classList.add('active');

		// Здесь можно добавить логику загрузки данных для выбранной вкладки
	});
});

// Пример функции для обновления счетчиков с анимацией
async function updateAccountCounters() {
	try {
		const response = await fetch('/accounts_count');
		const data = await response.json();

		// Обновляем основные счетчики
		document.querySelector('#all-folder .account-count').textContent = data.all;
		document
			.querySelector('#all-folder .account-count')
			.setAttribute('data-count', data.all);

		document.querySelector('#working-folder .account-count').textContent =
			data.working;
		document
			.querySelector('#working-folder .account-count')
			.setAttribute('data-count', data.working);

		document.querySelector('#archive-folder .account-count').textContent =
			data.archived;
		document
			.querySelector('#archive-folder .account-count')
			.setAttribute('data-count', data.archived);

		// Если в ответе есть данные о спаме, используем их
		if (data.no_spam !== undefined && data.with_spam !== undefined) {
			document.querySelector('#no-spam-folder .account-count').textContent =
				data.no_spam;
			document
				.querySelector('#no-spam-folder .account-count')
				.setAttribute('data-count', data.no_spam);

			document.querySelector('#with-spam-folder .account-count').textContent =
				data.with_spam;
			document
				.querySelector('#with-spam-folder .account-count')
				.setAttribute('data-count', data.with_spam);
		}
		// Иначе считаем вручную из таблицы
		else {
			const rows = document.querySelectorAll('#accounts-table tbody tr');
			let noSpamCount = 0;
			let withSpamCount = 0;

			rows.forEach(row => {
				if (row.style.display !== 'none') {
					const statusBadge = row.querySelector('.status-badge');
					if (statusBadge) {
						const status = statusBadge.classList[1];
						if (status === 'alive') noSpamCount++;
						if (status === 'spam-block') withSpamCount++;
					}
				}
			});

			document.querySelector('#no-spam-folder .account-count').textContent =
				noSpamCount;
			document
				.querySelector('#no-spam-folder .account-count')
				.setAttribute('data-count', noSpamCount);

			document.querySelector('#with-spam-folder .account-count').textContent =
				withSpamCount;
			document
				.querySelector('#with-spam-folder .account-count')
				.setAttribute('data-count', withSpamCount);
		}
	} catch (error) {
		console.error('Ошибка при получении данных:', error);
		// Можно показать уведомление об ошибке
	}
}

// Вызываем при загрузке страницы
document.addEventListener('DOMContentLoaded', function () {
	updateAccountCounters();
	setInterval(updateAccountCounters, 30000);
});

function openModal() {
	document.getElementById('pm-mailing-modal').classList.add('modal-open');
	document.body.style.overflow = 'hidden';
}

// Функция закрытия модального окна
function closeModal() {
	document.getElementById('pm-mailing-modal').classList.remove('modal-open');
	document.body.style.overflow = '';
}

function toggleAutoReplySettings() {
	const settings = document.getElementById('auto-reply-settings');
	settings.style.display = document.getElementById('auto-reply').checked
		? 'block'
		: 'none';
}

// Переключение поля для файла
function toggleFileInput() {
	const fileInput = document.getElementById('file-input-container');
	fileInput.style.display = document.getElementById('attach-file').checked
		? 'block'
		: 'none';
}

// Обработчик клавиши ESC
function handleEscKey(e) {
	if (e.key === 'Escape') {
		closePMMailingModal();
	}
}

// Функция для получения данных формы
function getFormData(modalId) {
	const modal = document.getElementById(modalId);
	if (!modal) return {};

	const formData = {};

	// Обрабатываем input, textarea, select
	modal
		.querySelectorAll(
			'input:not([type="checkbox"]):not([type="radio"]), textarea, select'
		)
		.forEach(el => {
			if (el.name) formData[el.name] = el.value;
			else if (el.id) formData[el.id] = el.value;
		});

	// Обрабатываем чекбоксы и радиокнопки
	modal
		.querySelectorAll('input[type="checkbox"], input[type="radio"]')
		.forEach(el => {
			if (el.name) formData[el.name] = el.checked;
			else if (el.id) formData[el.id] = el.checked;
		});

	// Обрабатываем файлы
	modal.querySelectorAll('input[type="file"]').forEach(el => {
		if (el.files.length > 0) {
			if (el.name) formData[el.name] = el.files[0];
			else if (el.id) formData[el.id] = el.files[0];
		}
	});

	return formData;
}

// Функции для toggle дополнительных настроек
function toggleAutoReplySettings() {
	const autoReplyCheckbox = document.getElementById('auto-reply');
	const autoReplySettings = document.getElementById('auto-reply-settings');

	if (autoReplyCheckbox.checked) {
		autoReplySettings.style.display = 'block';
	} else {
		autoReplySettings.style.display = 'none';
	}
}

function toggleFileInput() {
	const attachFileCheckbox = document.getElementById('attach-file');
	const fileInputContainer = document.getElementById('file-input-container');

	if (attachFileCheckbox.checked) {
		fileInputContainer.style.display = 'block';
	} else {
		fileInputContainer.style.display = 'none';
	}
}
document
	.getElementById('file-attachment')
	.addEventListener('change', function (e) {
		const statusElement = document.getElementById('file-selected-status');
		if (this.files.length > 0) {
			statusElement.style.display = 'block';
			statusElement.textContent = `Выбран файл: ${this.files[0].name}`;
		} else {
			statusElement.style.display = 'none';
		}
	});

function stopAutoResponder() {
	const sendButton = document.getElementById('send-button');
	sendButton.disabled = false;
	sendButton.textContent = 'Запустить Ловец Лидов';
	fetch('/stopAccounts', { method: 'GET' }).catch(error =>
		console.error('Request failed:', error)
	);
}

async function startAdding() {
	const sendButton = document.getElementById('send-button');
	const originalText = sendButton.textContent;

	try {
		sendButton.disabled = true;
		sendButton.textContent = 'Запуск...';

		const formData = new FormData();
		const selected = Array.from(selectedAccounts).map(
			index => accounts[index].phone
		);
		const proxies = getAllProxies();

		// Базовые параметры
		formData.append('account_ids', JSON.stringify(selected));
		formData.append('proxies', JSON.stringify(proxies));
		formData.append(
			'threads_count',
			document.getElementById('threads-count').value
		);

		// Парсинг задержки
		const delayRange = document.getElementById('delay-range').value.split('-');
		formData.append('delay_min', delayRange[0].trim());
		formData.append('delay_max', delayRange[1].trim());

		// Параметры инвайта
		formData.append(
			'invites_per_account',
			document.getElementById('invites-per-account').value
		);
		formData.append(
			'chat_link',
			document.getElementById('chat-link').value.trim()
		);
		formData.append('users_list', document.getElementById('users-list').value);

		closeModal();
		const response = await fetch('/start_invites', {
			method: 'POST',
			body: formData,
		});

		if (!response.ok) throw new Error(`Ошибка сервера: ${response.status}`);

		const result = await response.json();
		showNotification(
			result.message || 'Добавление пользователей запущено!',
			'success'
		);

		// Обновление статуса в интерфейсе
		updateLeadCatcherStatus(true);
	} catch (error) {
		console.error('Ошибка при запуске добавления:', error);
		showNotification(
			error.message.includes('задержка')
				? 'Некорректный формат задержки (используйте мин-макс)'
				: error.message,
			'error'
		);
	} finally {
		sendButton.disabled = false;
		sendButton.textContent = originalText;
	}
}

// Вспомогательные функции
function showNotification(message, type) {
	// Реализация показа уведомления (можно использовать toast-библиотеку или свой компонент)
	const notification = document.createElement('div');
	notification.className = `notification ${type}`;
	notification.textContent = message;
	document.body.appendChild(notification);

	setTimeout(() => {
		notification.remove();
	}, 5000);
}

function updateLeadCatcherStatus(isActive) {
	// Обновляем UI в соответствии со статусом
	const statusElement = document.getElementById('lead-catcher-status');
	if (statusElement) {
		statusElement.textContent = isActive ? 'Активен' : 'Неактивен';
		statusElement.className = isActive ? 'status-active' : 'status-inactive';
	}
}
