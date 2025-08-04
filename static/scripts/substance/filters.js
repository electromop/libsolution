// Класс для работы с фильтрами, динамически подстраивающийся под поля типа вещества

class FiltersManager {
  constructor(formId, filtersBlockId) {
    this.form = document.getElementById(formId);
    this.filtersBlock = document.getElementById(filtersBlockId);
    this.dynamicFieldsContainer = null; // контейнер для динамических фильтров
    this.currentType = null;
    this.fields = [];
    this.init();
  }

  init() {
    // Добавим контейнер для динамических фильтров, если его нет
    if (this.form && !this.form.querySelector('.dynamic-fields')) {
      this.dynamicFieldsContainer = document.createElement('div');
      this.dynamicFieldsContainer.className = 'row g-4 dynamic-fields';
      // Вставим перед кнопками управления фильтрами, если controls действительно является дочерним элементом формы
      const controls = this.form.querySelector('.col-12');
      if (controls && controls.parentNode === this.form) {
        this.form.insertBefore(this.dynamicFieldsContainer, controls);
      } else {
        // Если controls не найден или не является прямым потомком формы, просто добавляем в конец формы
        this.form.appendChild(this.dynamicFieldsContainer);
      }
    } else if (this.form) {
      this.dynamicFieldsContainer = this.form.querySelector('.dynamic-fields');
    }
  }

  // Установить текущий тип и поля (вызывается при выборе типа)
  async setType(type) {
    this.currentType = type;
    if (!type || !type.id) {
      this.fields = [];
      this.renderDynamicFields();
      return;
    }
    // Получаем поля типа с сервера
    try {
      const res = await fetch(`http://127.0.0.1:8000/types/${type.id}/fields`);
      if (!res.ok) throw new Error('Ошибка загрузки полей типа');
      this.fields = await res.json();
      this.renderDynamicFields();
    } catch (e) {
      console.error('Ошибка получения полей типа:', e);
      this.fields = [];
      this.renderDynamicFields();
    }
  }

  // Рендер динамических фильтров по полям типа
  renderDynamicFields() {
    if (!this.dynamicFieldsContainer) return;
    this.dynamicFieldsContainer.innerHTML = '';
    if (!this.fields || this.fields.length === 0) return;

    this.fields.forEach(field => {
      const col = document.createElement('div');
      col.className = 'col-lg-4 col-md-6';

      const group = document.createElement('div');
      group.className = 'filter-group p-3 rounded-3 border bg-light h-100';

      // Название поля
      const label = document.createElement('label');
      label.className = 'form-label fw-semibold mb-2';
      label.textContent = field.name + (field.unit ? ` (${field.unit})` : '');
      group.appendChild(label);

      // В зависимости от типа поля рендерим соответствующий фильтр
      switch (field.field_type) {
        case 'string':
        case 'enum':
          {
            // Для строк и enum: select для режима + input/select для значения
            const inputGroup = document.createElement('div');
            inputGroup.className = 'input-group';

            const selectMode = document.createElement('select');
            selectMode.className = 'form-select';
            selectMode.style.maxWidth = '120px';
            selectMode.name = `field_${field.name}_mode`;

            // Для enum только equals/in
            if (field.field_type === 'enum') {
              selectMode.innerHTML = `
                <option value="equals">Равно</option>
                <option value="not_equals">Не равно</option>
              `;
            } else {
              selectMode.innerHTML = `
                <option value="contains">Содержит</option>
                <option value="equals">Равно</option>
                <option value="not_equals">Не равно</option>
              `;
            }

            inputGroup.appendChild(selectMode);

            let valueInput;
            if (field.field_type === 'enum' && field.choices) {
              // Если есть choices (варианты), делаем select
              valueInput = document.createElement('select');
              valueInput.className = 'form-select';
              valueInput.name = `field_${field.name}`;
              field.choices.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt;
                option.textContent = opt;
                valueInput.appendChild(option);
              });
            } else {
              // Обычный input
              valueInput = document.createElement('input');
              valueInput.type = 'text';
              valueInput.className = 'form-control';
              valueInput.name = `field_${field.name}`;
              valueInput.placeholder = `Введите значение`;
            }
            inputGroup.appendChild(valueInput);
            group.appendChild(inputGroup);
          }
          break;
        case 'int':
        case 'float':
          {
            // Для числовых: два поля "от" и "до"
            const row = document.createElement('div');
            row.className = 'row g-2';

            const colFrom = document.createElement('div');
            colFrom.className = 'col';
            const inputFrom = document.createElement('input');
            inputFrom.type = 'number';
            inputFrom.className = 'form-control';
            inputFrom.name = `field_${field.name}_from`;
            inputFrom.placeholder = 'От';
            colFrom.appendChild(inputFrom);

            const colTo = document.createElement('div');
            colTo.className = 'col';
            const inputTo = document.createElement('input');
            inputTo.type = 'number';
            inputTo.className = 'form-control';
            inputTo.name = `field_${field.name}_to`;
            inputTo.placeholder = 'До';
            colTo.appendChild(inputTo);

            row.appendChild(colFrom);
            row.appendChild(colTo);
            group.appendChild(row);
          }
          break;
        case 'bool':
          {
            // Для bool: чекбокс "Да"/"Нет"
            const formCheck = document.createElement('div');
            formCheck.className = 'form-check';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.className = 'form-check-input';
            input.name = `field_${field.name}`;
            input.id = `filter_${field.name}`;
            const labelBool = document.createElement('label');
            labelBool.className = 'form-check-label fw-semibold';
            labelBool.htmlFor = `filter_${field.name}`;
            labelBool.textContent = 'Да';
            formCheck.appendChild(input);
            formCheck.appendChild(labelBool);
            group.appendChild(formCheck);
          }
          break;
        case 'date':
          {
            // Для даты: два поля "от" и "до"
            const row = document.createElement('div');
            row.className = 'row g-2';

            const colFrom = document.createElement('div');
            colFrom.className = 'col';
            const inputFrom = document.createElement('input');
            inputFrom.type = 'date';
            inputFrom.className = 'form-control';
            inputFrom.name = `field_${field.name}_from`;
            inputFrom.placeholder = 'От';
            colFrom.appendChild(inputFrom);

            const colTo = document.createElement('div');
            colTo.className = 'col';
            const inputTo = document.createElement('input');
            inputTo.type = 'date';
            inputTo.className = 'form-control';
            inputTo.name = `field_${field.name}_to`;
            inputTo.placeholder = 'До';
            colTo.appendChild(inputTo);

            row.appendChild(colFrom);
            row.appendChild(colTo);
            group.appendChild(row);
          }
          break;
        default:
          // Неизвестный тип, ничего не делаем
          break;
      }

      col.appendChild(group);
      this.dynamicFieldsContainer.appendChild(col);
    });
  }

  // Получить значения фильтров (включая динамические)
  getFilters() {
    const data = {};
    if (!this.form) return data;
    const formData = new FormData(this.form);
    for (let [key, value] of formData.entries()) {
      if (value !== '' && value !== null) {
        data[key] = value;
      }
    }
    // Для чекбоксов (bool) - если не отмечен, FormData не содержит, поэтому ищем вручную
    if (this.fields && this.fields.length > 0) {
      this.fields.forEach(field => {
        if (field.field_type === 'bool') {
          const name = `field_${field.name}`;
          const input = this.form.querySelector(`[name="${name}"]`);
          data[name] = input && input.checked ? true : false;
        }
      });
    }
    return data;
  }

  // Очистить все фильтры
  clearFilters() {
    if (!this.form) return;
    this.form.reset();
    // Сбросить чекбоксы динамических bool
    if (this.fields && this.fields.length > 0) {
      this.fields.forEach(field => {
        if (field.field_type === 'bool') {
          const name = `field_${field.name}`;
          const input = this.form.querySelector(`[name="${name}"]`);
          if (input) input.checked = false;
        }
      });
    }
  }
}



// Пример инициализации (вызывать после загрузки страницы и получения типа):
// const filtersManager = new FiltersManager('filtersForm', 'filtersBlock');
// filtersManager.setType({id: '...', ...}); // передать объект типа с id
