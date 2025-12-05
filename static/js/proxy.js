let proxies = []; // Массив для хранения прокси
let selectedProxies = new Set(); // Множество для хранения выбранных прокси

// Функция для отображения таблицы прокси
function renderProxyTable() {
	const tbody = document.querySelector('#proxy-table tbody');
	tbody.innerHTML = proxies
		.map(
			(proxy, index) => `
        <tr>
            <td class="selector-cell">
                <input type="checkbox" class="selector-checkbox" 
                    ${selectedProxies.has(index) ? 'checked' : ''}
                    data-index="${index}">
            </td>
            <td>${proxy.ip}</td>
            <td>${proxy.port}</td>
            <td>${proxy.login}</td>
            <td>${proxy.password}</td>
            <td>${proxy.url}</td>
        </tr>
    `
		)
		.join('');
	updateControls();
}

function saveProxiesToLocalStorage() {
	localStorage.setItem('proxies', JSON.stringify(proxies));
}

function loadProxiesFromLocalStorage() {
	const savedProxies = localStorage.getItem('proxies');
	if (savedProxies) {
		proxies = JSON.parse(savedProxies);
		renderProxyTable();
	}
}

// Функция для выбора/снятия выбора прокси
function toggleSelectProxy(index) {
	if (selectedProxies.has(index)) {
		selectedProxies.delete(index);
	} else {
		selectedProxies.add(index);
	}
	renderProxyTable();
}

// Функция для удаления выбранных прокси
function deleteSelectedProxies() {
	const selected = Array.from(selectedProxies);
	proxies = proxies.filter((_, index) => !selected.includes(index));
	selectedProxies.clear();
	saveProxiesToLocalStorage();
	renderProxyTable();
}

// Функция для добавления прокси
function addNewProxy() {
	const input = document.getElementById('new-proxy').value.trim();
	if (!input) {
		
		return;
	}

	const proxyLines = input.split('\n').filter(line => line.trim() !== '');

	proxyLines.forEach(line => {
		let ip, port, login, password, url;

		if (line.startsWith('http://')) {
			// Формат: http://login:pass@ip:port
			const parts = line.split('@');
			const credentials = parts[0].replace('http://', '').split(':');
			const address = parts[1].split(':');
			login = credentials[0];
			password = credentials[1];
			ip = address[0];
			port = address[1];
			url = line;
		} else {
			// Формат: ip:port:login:pass
			const parts = line.split(':');
			ip = parts[0];
			port = parts[1];
			login = parts[2];
			password = parts[3];
			url = `http://${login}:${password}@${ip}:${port}`;
		}

		proxies.push({ ip, port, login, password, url });
	});

	saveProxiesToLocalStorage();
	closeAddProxyForm();
	document.getElementById('new-proxy').value = '';
	renderProxyTable();
}

// Функции для модального окна
function showAddProxyForm() {
	document.getElementById('add-proxy-modal').style.display = 'flex';
}

function closeAddProxyForm() {
	document.getElementById('add-proxy-modal').style.display = 'none';
}

function toggleActionMenu() {
	const menu = document.getElementById('action-menu');
	menu.style.display = menu.style.display === 'flex' ? 'none' : 'flex';
}

async function runProxyChecker() {
	const proxyCheckBtn = document.getElementById('proxyCheckBtn');
	const originalHtml = proxyCheckBtn.innerHTML;

	// Меняем кнопку на состояние загрузки
	proxyCheckBtn.innerHTML = `
        <span class="spinner"></span>
        Идёт проверка...
    `;
	proxyCheckBtn.disabled = true;

	try {
		// Отправляем прокси на бэкенд
		const proxyUrls = Array.from(selectedProxies).map(
				index => proxies[index].url
			);
		if (proxyUrls.length === 0) {
			throw new Error('Не выбрано ни одного прокси для проверки');
		}
		const response = await fetch('/check_proxies', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({
				proxies: proxyUrls,
			}),
		});

		// Ждём ответа от бэкенда
		if (!response.ok) {
			const errorData = await response.json().catch(() => ({}));
			throw new Error(errorData.message || errorData.error || `Ошибка сервера: ${response.status}`);
		}
		
		const result = await response.json();
		
		if (result.status === false) {
			throw new Error(result.message || 'Ошибка проверки прокси');
		}
		
		// Обновляем статус прокси в интерфейсе
		if (result.results && Array.isArray(result.results)) {
			updateProxyStatus(result.results);
		}
		
		if (typeof showNotification === 'function') {
			showNotification(result.message || 'Прокси проверены', 'success');
		} else {
			alert(result.message || 'Прокси проверены');
		}
	} catch (error) {
		console.error('Ошибка:', error);
		if (typeof showNotification === 'function') {
			showNotification('Ошибка при проверке прокси: ' + error.message, 'error');
		} else {
			alert('Ошибка при проверке прокси: ' + error.message);
		}
	} finally {
		// Возвращаем кнопку в исходное состояние
		proxyCheckBtn.innerHTML = originalHtml;
		proxyCheckBtn.disabled = false;
	}
}

// Функция для обновления статуса прокси в таблице
function updateProxyStatus(results) {
	results.forEach((result, index) => {
		const [isWorking, proxyUrl] = result;
		// Находим прокси по URL и обновляем его статус
		const proxyIndex = proxies.findIndex(p => p.url === proxyUrl);
		if (proxyIndex !== -1) {
			proxies[proxyIndex].status = isWorking ? 'working' : 'failed';
			proxies[proxyIndex].lastChecked = new Date().toISOString();
		}
	});
	saveProxiesToLocalStorage();
	renderProxyTable();
}

document.getElementById('photo-input').addEventListener('change', function(e) {
  const fileLabel = document.getElementById('file-upload-label');
  const statusText = document.getElementById('file-status-text');
  const fileInfo = document.getElementById('selected-file-info');
  const fileName = document.getElementById('selected-file-name');
  const confirmBtn = document.getElementById('confirm-btn');
  
  if (this.files && this.files[0]) {
    // Показываем информацию о выбранном файле
    statusText.textContent = 'Файл выбран';
    fileName.textContent = this.files[0].name;
    fileInfo.style.display = 'flex';
    confirmBtn.disabled = false;
    
    // Изменяем стили label
    fileLabel.style.borderColor = '#28a745';
    fileLabel.style.backgroundColor = '#e8f5e9';
  } else {
    // Сбрасываем состояние
    statusText.textContent = 'Выберите файл';
    fileInfo.style.display = 'none';
    confirmBtn.disabled = true;
    fileLabel.style.borderColor = '#ccc';
    fileLabel.style.backgroundColor = 'transparent';
  }
});
	} catch (error) {
		console.error('Ошибка:', error);
		
	} finally {
		// Возвращаем кнопку в исходное состояние
		proxyCheckBtn.innerHTML = originalHtml;
		proxyCheckBtn.disabled = false;
	}
}



// Обновление состояния кнопок управления
function updateControls() {
	const controls = document.querySelector('.table-controls');
	const hasSelected = selectedProxies.size > 0;
	controls?.classList.toggle('has-selected', hasSelected);
}

// Выбрать все прокси
function selectAllProxies() {
	proxies.forEach((_, index) => selectedProxies.add(index));
	renderProxyTable();
}

// Снять выделение со всех прокси
function deselectAllProxies() {
	selectedProxies.clear();
	renderProxyTable();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
	loadProxiesFromLocalStorage();

	// Обработчики таблицы
	document.querySelector('#proxy-table')?.addEventListener('click', e => {
		const row = e.target.closest('tr');
		// Пропускаем заголовки и клики вне строк
		if (!row || row.parentNode.nodeName === 'THEAD') return;

		// Всегда находим чекбокс в строке
		const checkbox = row.querySelector('.selector-checkbox');
		if (checkbox) {
			const index = parseInt(checkbox.dataset.index);
			toggleSelectProxy(index);

			// Обновляем состояние чекбокса
			checkbox.checked = !checkbox.checked;

			// Предотвращаем двойное срабатывание
			e.stopPropagation();
		}
	});

	// Обработчики кнопок управления
	document
		.querySelector('.delete-selected')
		?.addEventListener('click', deleteSelectedProxies);
	document
		.querySelector('.add-new')
		?.addEventListener('click', showAddProxyForm);
	document
		.querySelector('.select-all')
		?.addEventListener('click', selectAllProxies);
	document
		.querySelector('.deselect-all')
		?.addEventListener('click', deselectAllProxies);

	// Закрытие модального окна
	document.getElementById('add-proxy-modal')?.addEventListener('click', e => {
		if (e.target === document.getElementById('add-proxy-modal')) {
			closeAddProxyForm();
		}
	});

	// Обработчик формы добавления
	document
		.querySelector('.add-proxy-form button')
		?.addEventListener('click', addNewProxy);
});


