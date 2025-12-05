function showAddAccountForm() {
	document.getElementById('add-account-modal').style.display = 'flex';
}

function closeAddAccountForm() {
	document.getElementById('add-account-modal').style.display = 'none';
}

let currentFolder = 'all';
let currentSpamFilter = null;
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
	const audioAttachment = document.getElementById('audio-attachment');
	const audioLabel = document.querySelector(
		'#audio-input-container .file-input-label'
	);
	const audioStatus = document.getElementById('audio-selected-status');
	const messagePreviewAudio = document.getElementById('message-preview-audio');

	if (audioAttachment && audioLabel) {
		// Клик по лейблу открывает выбор файла
		audioLabel.addEventListener('click', function (e) {
			if (e.target !== audioAttachment) {
				audioAttachment.click();
			}
		});

		// Обработка выбора голосового сообщения
		audioAttachment.addEventListener('change', function (e) {
			if (this.files.length > 0) {
				audioStatus.style.display = 'block';
				audioStatus.textContent = `Выбрано голосовое сообщение: ${this.files[0].name}`;
				// Показываем предпросмотр голосового сообщения
				if (messagePreviewAudio) {
					messagePreviewAudio.style.display = 'block';
				}
			} else {
				audioStatus.style.display = 'none';
				if (messagePreviewAudio) {
					messagePreviewAudio.style.display = 'none';
				}
			}
		});
	}
	loadAccounts(currentFolder);

	// Обработчики событий
	workingFolderBtn?.addEventListener('click', () => switchFolder('working'));
	archiveFolderBtn?.addEventListener('click', () => switchFolder('archive'));
	document.getElementById('no-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('no-spam');
		filterAccounts();
		updateAccountCounters();
	});

	document.getElementById('with-spam-folder')?.addEventListener('click', () => {
		toggleSpamFilter('with-spam');
		filterAccounts();
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

	// Обработчики для файла
	const fileAttachment = document.getElementById('file-attachment');
	const fileLabel = document.querySelector(
		'#file-input-container .file-input-label'
	);
	const fileStatus = document.getElementById('file-selected-status');

	if (fileAttachment && fileLabel) {
		fileLabel.addEventListener('click', function (e) {
			if (e.target !== fileAttachment) {
				fileAttachment.click();
			}
		});

		fileAttachment.addEventListener('change', function (e) {
			if (this.files.length > 0) {
				fileStatus.style.display = 'block';
				fileStatus.textContent = `Выбран файл: ${this.files[0].name}`;
			} else {
				fileStatus.style.display = 'none';
			}
		});
	}

	// Обработчики для кружочка
	const voiceAttachment = document.getElementById('voice-attachment');
	const voiceLabel = document.querySelector(
		'#voice-input-container .file-input-label'
	);
	const voiceStatus = document.getElementById('voice-selected-status');
	const messagePreviewVoice = document.getElementById('message-preview-voice');

	if (voiceAttachment && voiceLabel) {
		voiceLabel.addEventListener('click', function (e) {
			if (e.target !== voiceAttachment) {
				voiceAttachment.click();
			}
		});

		voiceAttachment.addEventListener('change', function (e) {
			if (this.files.length > 0) {
				voiceStatus.style.display = 'block';
				voiceStatus.textContent = `Выбран кружочек: ${this.files[0].name}`;
				if (messagePreviewVoice) {
					messagePreviewVoice.style.display = 'block';
				}
			} else {
				voiceStatus.style.display = 'none';
				if (messagePreviewVoice) {
					messagePreviewVoice.style.display = 'none';
				}
			}
		});
	}

	// Инициализация предпросмотра
	updateMessagePreview();
});

function switchFolder(folder) {
	currentFolder = folder;
	currentSpamFilter = null;
	updateButtons();
	loadAccounts(folder);
}

function toggleSpamFilter(filter) {
	currentSpamFilter = currentSpamFilter === filter ? null : filter;
	updateButtons();
	filterAccounts();
}

function updateButtons() {
	document
		.querySelectorAll('.account-folder-selector .account-folder-btn')
		.forEach(btn => {
			btn.classList.remove('active');
		});
	document.getElementById(`${currentFolder}-folder`)?.classList.add('active');

	if (currentSpamFilter) {
		document
			.getElementById(`${currentSpamFilter}-folder`)
			?.classList.add('active');
	}
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

		const shouldShow = folderMatch && spamMatch;
		row.style.display = shouldShow ? '' : 'none';
	});

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
		updateAccountCounters();
	} catch (error) {
		console.error('Ошибка загрузки аккаунтов:', error);
	}
}

function updateControls() {
	const controls = document.querySelector('.table-controls');
	const hasSelected = selectedAccounts.size > 0;
	controls?.classList.toggle('has-selected', hasSelected);
}

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

	document.querySelectorAll('.selector-checkbox').forEach(checkbox => {
		checkbox.addEventListener('change', function () {
			const index = parseInt(this.dataset.index);
			this.checked
				? selectedAccounts.add(index)
				: selectedAccounts.delete(index);
			updateControls();
		});
	});

	updateControls();
}

function selectAllAccounts() {
	if (selectedAccounts.size === accounts.length) {
		deselectAllAccounts();
		return;
	}

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

async function checkSpamBlock() {
	closeActionMenu();
	const success = await postSelectedAccounts('/check_spam_block');
	if (success) {
		loadAccounts(currentFolder);
	}
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

async function openInWebNumber(phoneNumber) {
	const proxies = getAllProxies();
	const data = {
		account_ids: Array.of(phoneNumber),
		proxies: JSON.stringify(proxies),
		current_folder: currentFolder,
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
		console.error('Ошибка:', error);
		return false;
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
	open: (modalId, callback) => {
		const modal = document.getElementById(modalId);
		modal.style.display = 'block';

		const input = modal.querySelector('input');
		if (input) input.focus();

		modal.querySelector('.confirm-btn').onclick = async () => {
			try {
				await callback();
			} catch (error) {
				console.error('Error:', error);
			}
		};

		modal.onclick = e => {
			if (e.target === modal) ModalManager.close(modalId);
		};
	},

	close: modalId => {
		document.getElementById(modalId).style.display = 'none';
	},

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
	const confirmBtn = document.querySelector('#edit-photo-modal .confirm-btn');

	if (this.files && this.files[0]) {
		statusElement.style.display = 'block';
		if (confirmBtn) confirmBtn.disabled = false;
	} else {
		statusElement.style.display = 'none';
		if (confirmBtn) confirmBtn.disabled = true;
	}
});

document.querySelectorAll('.account-folder-btn').forEach(btn => {
	btn.addEventListener('click', function () {
		document.querySelectorAll('.account-folder-btn').forEach(b => {
			b.classList.remove('active');
		});
		this.classList.add('active');
	});
});

async function updateAccountCounters() {
	try {
		const response = await fetch('/accounts_count');
		const data = await response.json();

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
		} else {
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
	}
}

// Модальное окно рассылки
function openModal() {
	document.getElementById('pm-mailing-modal').classList.add('modal-open');
	document.body.style.overflow = 'hidden';
}

function closeModal() {
	document.getElementById('pm-mailing-modal').classList.remove('modal-open');
	document.body.style.overflow = '';
}

// Функции toggle для настроек
function toggleAutoReplySettings() {
	const settings = document.getElementById('auto-reply-settings');
	settings.style.display = document.getElementById('auto-reply').checked
		? 'block'
		: 'none';
}

function toggleFileInput() {
	const fileCheckbox = document.getElementById('attach-file');
	const fileInputContainer = document.getElementById('file-input-container');
	const voiceCheckbox = document.getElementById('attach-voice');
	const voiceInputContainer = document.getElementById('voice-input-container');

	if (fileCheckbox.checked) {
		fileInputContainer.style.display = 'block';
		voiceCheckbox.checked = false;
		voiceInputContainer.style.display = 'none';
	} else {
		fileInputContainer.style.display = 'none';
	}
}

function toggleVoiceInput() {
	const voiceCheckbox = document.getElementById('attach-voice');
	const voiceInputContainer = document.getElementById('voice-input-container');
	const fileCheckbox = document.getElementById('attach-file');
	const fileInputContainer = document.getElementById('file-input-container');

	if (voiceCheckbox.checked) {
		voiceInputContainer.style.display = 'block';
		fileCheckbox.checked = false;
		fileInputContainer.style.display = 'none';
	} else {
		voiceInputContainer.style.display = 'none';
	}
}

function stopAutoResponder() {
	fetch('/stopAccounts', { method: 'GET' }).catch(error =>
		console.error('Request failed:', error)
	);
}

function toggleAudioInput() {
	const audioCheckbox = document.getElementById('attach-audio');
	const audioInputContainer = document.getElementById('audio-input-container');
	const fileCheckbox = document.getElementById('attach-file');
	const fileInputContainer = document.getElementById('file-input-container');
	const voiceCheckbox = document.getElementById('attach-voice');
	const voiceInputContainer = document.getElementById('voice-input-container');

	if (audioCheckbox.checked) {
		audioInputContainer.style.display = 'block';
		// Отключаем другие типы вложений
		fileCheckbox.checked = false;
		fileInputContainer.style.display = 'none';
		voiceCheckbox.checked = false;
		voiceInputContainer.style.display = 'none';
	} else {
		audioInputContainer.style.display = 'none';
	}
}

async function startPMMailing() {
	const sendButton = document.getElementById('send-button') || document.getElementById('start-dm-btn') || document.getElementById('do-start-dm-btn');
	if (!sendButton) {
		if (typeof showNotification === 'function') {
			showNotification('Кнопка запуска не найдена', 'error');
		} else {
			alert('Кнопка запуска не найдена');
		}
		return;
	}
	const originalText = sendButton.textContent || sendButton.innerHTML;

	try {
		sendButton.disabled = true;
		sendButton.textContent = 'Отправка...';

		const formData = new FormData();
		const selected = Array.from(selectedAccounts).map(
			index => accounts[index].phone
		);
		const proxies = getAllProxies();

		formData.append('account_ids', JSON.stringify(selected));
		formData.append('current_folder', currentFolder);
		formData.append('proxies', JSON.stringify(proxies));

		// Основные параметры
		formData.append(
			'threads_count',
			document.getElementById('threads-count').value
		);
		formData.append('min_delay', document.getElementById('min-delay').value);
		formData.append('max_delay', document.getElementById('max-delay').value);
		formData.append(
			'messages_per_account',
			document.getElementById('messages-per-account').value
		);
		formData.append(
			'recipients',
			document.getElementById('recipients-list').value
		);
		formData.append(
			'message_text',
			document.getElementById('message-text').value
		);

		// Новая опция удаления сообщения
		formData.append(
			'delete_after_send',
			document.getElementById('delete-after-send').checked
		);

		// Автоответчик
		const autoReplyEnabled = document.getElementById('auto-reply').checked;
		formData.append('auto_reply_enabled', autoReplyEnabled);
		if (autoReplyEnabled) {
			formData.append(
				'manager_chat',
				document.getElementById('manager-chat').value
			);
			formData.append(
				'reply_message',
				document.getElementById('reply-message').value
			);
		}

		// Проверяем тип вложения
		const attachFile = document.getElementById('attach-file').checked;
		const attachVoice = document.getElementById('attach-voice').checked;
		const attachAudio = document.getElementById('attach-audio').checked;

		if (attachFile) {
			const fileInput = document.getElementById('file-attachment');
			if (fileInput.files.length > 0) {
				formData.append('attachment', fileInput.files[0]);
				formData.append('attachment_type', 'file');
			}
		} else if (attachVoice) {
			const voiceInput = document.getElementById('voice-attachment');
			if (voiceInput.files.length > 0) {
				formData.append('attachment', voiceInput.files[0]);
				formData.append('attachment_type', 'voice');
			}
		} else if (attachAudio) {
			const audioInput = document.getElementById('audio-attachment');
			if (audioInput.files.length > 0) {
				formData.append('attachment', audioInput.files[0]);
				formData.append('attachment_type', 'audio');
			}
		}

		const response = await fetch('/startpmmailing', {
			method: 'POST',
			body: formData,
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			throw new Error(errorData.message || errorData.error || `Ошибка сервера: ${response.status}`);
		}

		const result = await response.json();
		console.log('Рассылка начата:', result);

		if (result.status === false) {
			throw new Error(result.message || 'Ошибка запуска рассылки');
		}

		// Закрываем модальное окно, если оно есть
		const modal = document.getElementById('dmTaskModal');
		if (modal) {
			modal.style.display = 'none';
		}
		
		if (typeof showNotification === 'function') {
			showNotification(result.message || 'Рассылка успешно запущена!', 'success');
		} else {
			alert(result.message || 'Рассылка успешно запущена!');
		}
	} catch (error) {
		console.error('Ошибка:', error);
		if (typeof showNotification === 'function') {
			showNotification('Произошла ошибка при отправке: ' + error.message, 'error');
		} else {
		alert('Произошла ошибка при отправке: ' + error.message);
		}
	} finally {
		if (sendButton) {
		sendButton.disabled = false;
			if (sendButton.textContent !== undefined) {
		sendButton.textContent = originalText;
			} else if (sendButton.innerHTML !== undefined) {
				sendButton.innerHTML = originalText;
			}
		}
	}
}


// Закрытие модального окна по ESC
document.addEventListener('keydown', function (e) {
	if (e.key === 'Escape') {
		const modal = document.getElementById('pm-mailing-modal');
		if (modal && modal.classList.contains('modal-open')) {
			closeModal();
		}
	}
});
