// js/ai_agents.js - Vanilla JS implementation with file upload, modal centering, and fixed edit

let agents = [];
let currentAgent = null;
let isEditMode = false;

// Elements
const agentsListEl = document.querySelector('.agents-list');
const agentModal = document.getElementById('agentModal');
const modalContent = agentModal.querySelector('.modal-content');
const modalTitleEl = agentModal.querySelector('h3');
const nameInput = agentModal ? agentModal.querySelector('#agent-name-input') : null;
const modelSelect = agentModal ? agentModal.querySelector('#agent-model-select') : null;
const promptTextarea = agentModal ? agentModal.querySelector('#agent-prompt-textarea') : null;
const examplesContainer = agentModal.querySelector('.dialogue-examples');
const btnAddExample = agentModal.querySelector('.btn-add-example');
const btnCancel = agentModal.querySelector('.btn-cancel');
const btnSave = agentModal.querySelector('.btn-save');
const btnCreateAgent = document.querySelector('.btn-create-agent');

// File upload elements

const fileInput = document.createElement('input');
fileInput.type = 'file';
fileInput.accept = 'application/json';
fileInput.style.display = 'none';



// Initialize
document.addEventListener('DOMContentLoaded', () => {
	if (!agentModal || !nameInput || !modelSelect || !promptTextarea) {
		console.error('Не найдены необходимые элементы DOM');
		return;
	}
	
	fetchAgents();
	if (btnCreateAgent) {
	btnCreateAgent.addEventListener('click', showAgentCreationForm);
	}
	// Также добавляем обработчик для onclick в HTML
	if (typeof window.showAgentCreationForm === 'undefined') {
		window.showAgentCreationForm = showAgentCreationForm;
	}
	if (typeof window.hideAgentModal === 'undefined') {
		window.hideAgentModal = hideAgentModal;
	}
	if (btnCancel) {
	btnCancel.addEventListener('click', hideAgentModal);
	}
	if (btnAddExample) {
	btnAddExample.addEventListener('click', addExample);
	}
	if (btnSave) {
	btnSave.addEventListener('click', saveAgent);
	}
	if (fileInput) {
	fileInput.addEventListener('change', handleFileUpload);
	}

	// Delegated edit/delete handlers
	if (agentsListEl) {
	agentsListEl.addEventListener('click', event => {
		const card = event.target.closest('.agent-card');
		if (!card) return;
		const id = card.dataset.id;
		const agent = agents.find(a => String(a.id) === id);
		if (event.target.classList.contains('btn-edit')) editAgent(agent);
		if (event.target.classList.contains('btn-delete')) deleteAgent(agent);
	});
	}
});

// Fetch agents from API
function fetchAgents() {
	fetch('/api/agents')
		.then(res => res.json())
		.then(data => {
			agents = data;
			renderAgents();
		})
		.catch(err => {
			console.error('Ошибка при получении агентов:', err);
			if (typeof showNotification === 'function') {
				showNotification('Ошибка при загрузке агентов: ' + err.message, 'error');
			}
		});
}

// Render agent cards
function renderAgents() {
	agentsListEl.innerHTML = '';
	agents.forEach(agent => {
		const card = document.createElement('div');
		card.className = 'agent-card';
		card.dataset.id = agent.id;

		const header = document.createElement('div');
		header.className = 'agent-header';
		header.innerHTML = `
      <h3>${agent.name || 'Без названия'}</h3>
      <div class="agent-actions">
        <button class="btn-edit" style="margin-right: 8px;">✏️</button>
        <button class="btn-delete">🗑</button>
      </div>
    `;
		card.appendChild(header);

		const details = document.createElement('div');
		details.className = 'agent-details';
		details.innerHTML = `
      <p><strong>Модель:</strong> ${agent.model}</p>
      <p><strong>Примеры диалогов:</strong> ${agent.examples.length}</p>
    `;
		card.appendChild(details);

		agentsListEl.appendChild(card);
	});
}

// Show modal for creation
function showAgentCreationForm() {
	isEditMode = false;
	currentAgent = {
		id: null,
		name: '',
		model: 'gpt-4',
		prompt: '',
		examples: [],
	};
	openModal();
}

// Edit existing agent
function editAgent(agent) {
	if (!agent) return;
	isEditMode = true;
	currentAgent = JSON.parse(JSON.stringify(agent));
	openModal();
}

// Handle file upload JSON
function handleFileUpload(e) {
	const file = e.target.files[0];
	if (!file) return;
	const reader = new FileReader();
	reader.onload = evt => {
		try {
			const data = JSON.parse(evt.target.result);
			currentAgent = {
				id: data.id || null,
				name: data.name || '',
				model: data.model || 'gpt-4',
				prompt: data.prompt || '',
				examples: data.examples || [],
			};
			isEditMode = !!data.id;
			openModal();
		} catch (err) {
			alert('Ошибка чтения файла: неверный формат JSON');
		}
	};
	reader.readAsText(file);
	fileInput.value = '';
}

// Open and populate modal
function openModal() {
	if (!agentModal) {
		console.error('Не найдено модальное окно');
		if (typeof showNotification === 'function') {
			showNotification('Ошибка: не найдено модальное окно', 'error');
		}
		return;
	}
	
	// Обновляем элементы если они еще не найдены
	if (!nameInput) {
		const nameInputEl = agentModal.querySelector('#agent-name-input');
		if (nameInputEl) nameInput = nameInputEl;
	}
	if (!modelSelect) {
		const modelSelectEl = agentModal.querySelector('#agent-model-select');
		if (modelSelectEl) modelSelect = modelSelectEl;
	}
	if (!promptTextarea) {
		const promptTextareaEl = agentModal.querySelector('#agent-prompt-textarea');
		if (promptTextareaEl) promptTextarea = promptTextareaEl;
	}
	
	if (modalTitleEl) {
	modalTitleEl.textContent = isEditMode
		? 'Редактирование агента'
		: 'Создание агента';
	}
	if (nameInput) nameInput.value = currentAgent.name || '';
	if (modelSelect) modelSelect.value = currentAgent.model || 'gpt-4';
	if (promptTextarea) promptTextarea.value = currentAgent.prompt || '';
	renderExamples();
	// Center modal
	if (modalContent) {
	modalContent.style.position = 'fixed';
	modalContent.style.top = '50%';
	modalContent.style.left = '50%';
	modalContent.style.transform = 'translate(-50%, -50%)';
	}
	agentModal.style.display = 'block';
}

// Hide modal
function hideAgentModal() {
	agentModal.style.display = 'none';
}

// Render dialogue examples inputs
function renderExamples() {
	if (!examplesContainer) {
		examplesContainer = agentModal ? agentModal.querySelector('.dialogue-examples') : null;
		if (!examplesContainer) {
			console.error('Не найден контейнер для примеров');
			return;
		}
	}
	
	examplesContainer
		.querySelectorAll('.dialogue-pair')
		.forEach(el => el.remove());
	currentAgent.examples.forEach((example, idx) => {
		const pair = document.createElement('div');
		pair.className = 'dialogue-pair';

		const qInput = document.createElement('input');
		qInput.type = 'text';
		qInput.placeholder = 'Вопрос';
		qInput.value = example.question;
		qInput.addEventListener(
			'input',
			e => (currentAgent.examples[idx].question = e.target.value)
		);

		const rInput = document.createElement('input');
		rInput.type = 'text';
		qInput.placeholder = 'Ответ';
		rInput.value = example.response;
		rInput.addEventListener(
			'input',
			e => (currentAgent.examples[idx].response = e.target.value)
		);

		const btnRemove = document.createElement('button');
		btnRemove.className = 'btn-remove';
		btnRemove.textContent = '×';
		btnRemove.addEventListener('click', () => removeExample(idx));

		pair.append(qInput, rInput, btnRemove);
		examplesContainer.insertBefore(pair, btnAddExample);
	});
}

// Add new example
function addExample() {
	if (!currentAgent) {
		currentAgent = { examples: [] };
	}
	if (!currentAgent.examples) {
		currentAgent.examples = [];
	}
	currentAgent.examples.push({ question: '', response: '' });
	renderExamples();
}

// Remove example by index
function removeExample(index) {
	currentAgent.examples.splice(index, 1);
	renderExamples();
}

// Save agent via API
function saveAgent() {
	if (!nameInput || !modelSelect || !promptTextarea) {
		if (typeof showNotification === 'function') {
			showNotification('Ошибка: не найдены элементы формы', 'error');
		} else {
			alert('Ошибка: не найдены элементы формы');
		}
		return;
	}
	
	currentAgent.name = nameInput.value.trim();
	currentAgent.model = modelSelect.value;
	currentAgent.prompt = promptTextarea.value.trim();
	
	if (!currentAgent.name) {
		if (typeof showNotification === 'function') {
			showNotification('Введите название агента', 'warning');
		} else {
			alert('Введите название агента');
		}
		return;
	}

	const url = isEditMode ? `/api/agents/${currentAgent.id}` : '/api/agents';
	const method = isEditMode ? 'PUT' : 'POST';

	fetch(url, {
		method,
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(currentAgent),
	})
		.then(res => {
			if (!res.ok) throw new Error('Network response was not ok');
			return res.json();
		})
		.then(() => {
			hideAgentModal();
			fetchAgents();
		})
		.catch(err => console.error('Ошибка при сохранении агента:', err));
}

// Delete agent
function deleteAgent(agent) {
	if (!confirm(`Удалить агента "${agent.name}"?`)) return;
	fetch(`/api/agents/${agent.id}`, { method: 'DELETE' })
		.then(res => {
			if (res.ok) fetchAgents();
			else console.error('Ошибка при удалении агента');
		})
		.catch(err => console.error('Ошибка при удалении агента:', err));
}


function importFromFile(event) {
	const file = event.target.files[0];
	const fileNameSpan = document.getElementById('fileName');
	if (file) {
		if (fileNameSpan) fileNameSpan.textContent = file.name;

		const reader = new FileReader();
		reader.onload = function (e) {
			try {
				const json = JSON.parse(e.target.result);
				currentAgent = {
					id: json.id || null,
					name: json.name || '',
					model: json.model || 'gpt-4',
					prompt: json.prompt || '',
					examples: Array.isArray(json.examples) ? json.examples : [],
				};
				isEditMode = !!currentAgent.id;
				openModal();
			} catch (error) {
				if (typeof showNotification === 'function') {
					showNotification('Ошибка при чтении файла. Убедитесь, что это корректный JSON.', 'error');
				} else {
				alert('Ошибка при чтении файла. Убедитесь, что это корректный JSON.');
				}
			}
		};
		reader.readAsText(file);
	} else {
		if (fileNameSpan) fileNameSpan.textContent = 'Файл не выбран';
	}
}

// Делаем функцию доступной глобально
if (typeof window.importFromFile === 'undefined') {
	window.importFromFile = importFromFile;
}
