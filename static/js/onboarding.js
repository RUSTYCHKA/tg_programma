// onboarding.js - Система обучения для TeleRocket

class OnboardingSystem {
	constructor() {
		this.currentStep = 0;
		this.steps = [
			{
				type: 'welcome',
				content: {
					title: 'Привет!',
					subtitle: 'Спасибо, что используешь TeleRocket',
					description:
						'Я могу показать, как тут всё устроено. Это займет всего 30 секунд.',
				},
			},
			{
				type: 'highlight',
				targets: [
					'.proxy-table',
					'.card.mb-3',
					'.account-folder-btn',
					'.table-filters-panel',
				],
				content: {
					description:
						'Тут будет список твоих аккаунтов.\nМожно выделить нужные аккаунты и\nзапустить некоторые задачи прямо\nздесь.',
				},
				position: 'center',
			},
			{
				type: 'pointer',
				target: '.sidebar',
				content: {
					description: 'Для более сложных задач есть\nотдельные модули.',
				},
				position: 'right',
			},
			{
				type: 'pointer',
				target: '.table-filters-panel',
				content: {
					description:
						'Чтобы было проще искать нужные\nаккаунты, у нас есть много разных\nфильтров.',
				},
				position: 'bottom',
			},
			{
				type: 'pointer',
				target: '.account-folder-btn',
				content: {
					description:
						'Также сверху есть несколько быстрых\nфильтров — просто нажми на них для\nактивации.',
				},
				position: 'bottom',
			},
			{
				type: 'notification',
				content: {
					title: 'Перед началом работы',
					description: 'Нужно добавить прокси',
				},
			},
		];
		this.overlay = null;
		this.modal = null;
		this.init();
	}

	init() {
		// Проверяем, проходил ли пользователь онбординг
		const completed = localStorage.getItem('onboarding_completed');
		if (!completed) {
			this.start();
		}
	}

	start() {
		this.createOverlay();
		this.showStep(0);
	}

	createOverlay() {
		// Создаем затемнение
		this.overlay = document.createElement('div');
		this.overlay.className = 'onboarding-overlay';
		document.body.appendChild(this.overlay);
	}

	removeOverlay() {
		if (this.overlay) {
			this.overlay.remove();
			this.overlay = null;
		}
		this.removeHighlights();
		if (this.modal) {
			this.modal.remove();
			this.modal = null;
		}
	}

	showStep(stepIndex) {
		this.currentStep = stepIndex;
		const step = this.steps[stepIndex];

		// Убираем предыдущие подсветки
		this.removeHighlights();
		if (this.modal) {
			this.modal.remove();
		}

		switch (step.type) {
			case 'welcome':
				this.showWelcomeModal(step);
				break;
			case 'highlight':
				this.highlightElements(step);
				this.showTooltip(step);
				break;
			case 'pointer':
				this.showPointer(step);
				break;
			case 'notification':
				this.showNotification(step);
				break;
		}
	}

	showWelcomeModal(step) {
		this.modal = document.createElement('div');
		this.modal.className = 'onboarding-welcome-modal';
		this.modal.innerHTML = `
        <div class="onboarding-welcome-content">
            <div class="onboarding-welcome-left">
                <div class="rocket-animation">
                    <img src="static/images/onboarding.png" alt="MAN" />
                </div>
            </div>
            <div class="onboarding-welcome-right">
                <h2>${step.content.title}</h2>
                <h3>${step.content.subtitle}</h3>
                <p>${step.content.description}</p>
                <div class="onboarding-welcome-buttons">
                    <button class="onboarding-btn-secondary" onclick="onboardingSystem.skip()">Нет спасибо</button>
                    <button class="onboarding-btn-primary" onclick="onboardingSystem.next()">Посмотреть</button>
                </div>
            </div>
        </div>
    `;
		document.body.appendChild(this.modal);
	}

	highlightElements(step) {
		step.targets.forEach(selector => {
			const elements = document.querySelectorAll(selector);
			elements.forEach(el => {
				el.classList.add('onboarding-highlight');
			});
		});
	}

	showTooltip(step) {
		this.modal = document.createElement('div');
		this.modal.className = 'onboarding-tooltip onboarding-tooltip-center';
		this.modal.innerHTML = `
            <div class="onboarding-tooltip-content">
                <p>${step.content.description.replace(/\n/g, '<br>')}</p>
                <button class="onboarding-btn-primary" onclick="onboardingSystem.next()">
                    Дальше
                </button>
            </div>
        `;
		document.body.appendChild(this.modal);
	}

	showPointer(step) {
		const target = document.querySelector(step.target);
		if (!target) {
			this.next();
			return;
		}

		target.classList.add('onboarding-highlight');
		const rect = target.getBoundingClientRect();

		this.modal = document.createElement('div');
		this.modal.className = `onboarding-tooltip onboarding-tooltip-${step.position}`;

		// Позиционирование
		let top, left;
		switch (step.position) {
			case 'right':
				top = rect.top + rect.height / 2;
				left = rect.right + 20;
				break;
			case 'bottom':
				top = rect.bottom + 20;
				left = rect.left + rect.width / 2;
				break;
			case 'left':
				top = rect.top + rect.height / 2;
				left = rect.left - 20;
				break;
			default:
				top = rect.top - 20;
				left = rect.left + rect.width / 2;
		}

		this.modal.style.top = `${top}px`;
		this.modal.style.left = `${left}px`;

		this.modal.innerHTML = `
            <div class="onboarding-tooltip-arrow"></div>
            <div class="onboarding-tooltip-content">
                <p>${step.content.description.replace(/\n/g, '<br>')}</p>
                <button class="onboarding-btn-primary" onclick="onboardingSystem.next()">
                    Дальше
                </button>
            </div>
        `;
		document.body.appendChild(this.modal);
	}

	showNotification(step) {
		this.removeOverlay();

		this.modal = document.createElement('div');
		this.modal.className = 'onboarding-notification';
		this.modal.innerHTML = `
            <div class="onboarding-notification-content">
                <div class="onboarding-notification-icon">
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                </div>
                <div class="onboarding-notification-text">
                    <h3>${step.content.title}</h3>
                    <p>${step.content.description}</p>
                </div>
                <button class="onboarding-btn-primary" onclick="onboardingSystem.complete()">
                    Добавить прокси
                </button>
            </div>
        `;
		document.body.appendChild(this.modal);

		setTimeout(() => {
			this.modal.classList.add('show');
		}, 100);
	}

	removeHighlights() {
		document.querySelectorAll('.onboarding-highlight').forEach(el => {
			el.classList.remove('onboarding-highlight');
		});
	}

	next() {
		if (this.currentStep < this.steps.length - 1) {
			this.showStep(this.currentStep + 1);
		} else {
			this.complete();
		}
	}

	skip() {
		localStorage.setItem('onboarding_completed', 'true');
		this.removeOverlay();
	}

	complete() {
		localStorage.setItem('onboarding_completed', 'true');
		localStorage.setItem('open_proxy_modal', 'true');
		this.removeOverlay();

		// Сохраняем флаг, что онбординг завершился с необходимостью открыть прокси

		// Перенаправляем на страницу прокси
		window.location.href = '/proxy';
	}
}

// Инициализация при загрузке страницы
let onboardingSystem;
document.addEventListener('DOMContentLoaded', () => {
	onboardingSystem = new OnboardingSystem();
});
