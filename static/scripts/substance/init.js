const typeListElement = document.getElementById('typeList');
if (!typeListElement) {
    console.error('Element с id "typeList" не найден.');
    // Не продолжаем инициализацию, если нет нужного элемента
} else {
    // Создаём менеджеры и делаем modalManager глобальным для доступа из HTML
    window.typeManager = new TypeManager();
    window.modalManager = new ModalManager(window.typeManager);
}

const fieldsModal = document.getElementById('fieldsModal')

fieldsModal.addEventListener('shown.bs.modal', () => {
    modalManager.renderFieldsList();
})
const addItemModal = document.getElementById('addItemModal');
if (addItemModal) {
    addItemModal.addEventListener('shown.bs.modal', () => {
        // При открытии модального окна добавления элемента обновляем форму
        if (window.typeManager) {
            window.typeManager.renderItemForm();
        }
    });
}


// --- Инициализация фильтров ---
let filtersManager = null;

document.addEventListener('DOMContentLoaded', () => {
    const filtersForm = document.getElementById('filtersForm');
    const filtersBlock = document.getElementById('filtersBlock');
    const toggleFiltersBtn = document.getElementById('toggleFiltersBtn');

    // Инициализируем FiltersManager, если форма фильтров есть на странице
    if (filtersForm && filtersBlock) {
        filtersManager = new FiltersManager('filtersForm', 'filtersBlock');
        window.filtersManager = filtersManager; // делаем глобальным для отладки/доступа

        // При нажатии на кнопку фильтров прогружаем фильтры для текущего типа
        if (toggleFiltersBtn) {
            toggleFiltersBtn.addEventListener('click', async () => {
                if (window.typeManager && window.typeManager.currentType) {
                    await filtersManager.setType(window.typeManager.currentType);
                } else {
                    // Если тип не выбран, очищаем динамические фильтры
                    await filtersManager.setType(null);
                }
            });
        }
    }

    // Кнопка "Применить" фильтры
    if (filtersForm) {
        filtersForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (window.filtersManager) {
                const filters = window.filtersManager.getFilters();
                if (window.typeManager && window.typeManager.currentType) {
                    try {
                        const payload = { type_id: String(window.typeManager.currentType), filters };
                        const res = await fetch('/items/filter', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                        if (!res.ok) throw new Error('Ошибка применения фильтров');
                        const items = await res.json();
                        // Найдём объект типа по текущему id
                        const typeObj = window.typeManager.types.find(t => String(t.id) === String(window.typeManager.currentType));
                        if (typeObj) {
                            window.typeManager.renderItemsTable(items, typeObj);
                        }
                    } catch (err) {
                        console.error(err);
                    }
                }
            }
        });
    }

    // Кнопка "Сбросить" фильтры
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    if (clearFiltersBtn && filtersManager) {
        clearFiltersBtn.addEventListener('click', async function() {
            filtersManager.clearFilters();
            // После сброса показать все элементы выбранного типа
            if (window.typeManager && window.typeManager.currentType) {
                try {
                    await window.typeManager.renderTypeView();
                } catch (e) {
                    console.error('Не удалось перерисовать список после сброса фильтров', e);
                }
            }
        });
    }
});

