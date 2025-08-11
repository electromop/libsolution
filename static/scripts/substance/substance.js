// Последовательность применения комментариев:
// 1. Класс TypeManager: общий комментарий
// 2. constructor
// 3. init
// 4. fetchTypes
// 5. renderTypeList
// 6. renderTypeView
// 7. renderItemsTable
// 8. renderItemForm
// 9. getInputType
// 10. collectFormData
// 11. clearCurrentTypeView

/**
 * Класс TypeManager управляет типами, их отображением, выбором и добавлением элементов.
 * currentType теперь содержит id выбранного типа (берётся из url), а не объект типа.
 */
class TypeManager {
  /**
   * Конструктор инициализирует список типов и текущий выбранный тип (id), а также запускает инициализацию.
   */
  constructor() {
    this.types = [];
    this.currentType = null; // теперь это id типа
    this.init();
  }

  /**
   * Получает id типа из url (например, ?type_id=3 или /types/3/).
   * @returns {string|null}
   */
  getTypeIdFromUrl() {
    // Сначала ищем ?type_id=... в query string
    const params = new URLSearchParams(window.location.search);
    if (params.has('type_id')) {
      return params.get('type_id');
    }
    // Затем ищем /types/ID/ в pathname
    const match = window.location.pathname.match(/\/types\/(\d+)\//);
    if (match) {
      return match[1];
    }
    return null;
  }

  /**
   * Асинхронная инициализация: загружает типы, определяет текущий id типа из url, рендерит список типов.
   * Если в url уже есть type_id, сразу отображает таблицу и детали типа.
   */
  async init() {
    // Получаем id типа из url ДО загрузки типов
    this.currentType = this.getTypeIdFromUrl();
    await this.fetchTypes();
    // Если type_id есть в url и такой тип существует, сразу показываем детали
    if (this.currentType) {
      const found = this.types.find(t => String(t.id) === String(this.currentType));
      if (found) {
        this.renderTypeView();
      } else {
        this.currentType = null;
        this.clearCurrentTypeView();
      }
    }
    // Рендерим список типов всегда
    window.onload = () => this.renderTypeList();
  }

  /**
   * Загружает список типов с сервера, обновляет их в состоянии, рендерит список.
   * Если выбран тип, ничего не делает дополнительно — init сам вызывает renderTypeView при необходимости.
   */
  async fetchTypes() {
    const res = await fetch('/types/');
    this.types = await res.json();
    this.renderTypeList();
    // Не вызываем renderTypeView здесь, чтобы избежать двойного вызова при инициализации
  }

  /**
   * Отображает список всех типов в элементе typeList. Если типов нет — показывает сообщение.
   * При клике на тип выбирает его (id) и отображает подробности, а также обновляет url.
   */
  renderTypeList() {
    const list = document.getElementById('typeList');
    if (!list) {
      console.error('Element с id "typeList" не найден.');
      return;
    }
    list.innerHTML = '';
    if (this.types.length === 0) {
      const li = document.createElement('li');
      li.textContent = 'Нет типов';
      li.className = 'empty-message';
      list.appendChild(li);
      this.clearCurrentTypeView();
      return;
    }
    this.types.forEach(t => {
      const li = document.createElement('a');
      li.textContent = t.name;
      li.className = 'list-group-item list-group-item-action';
      if (this.currentType && String(this.currentType) === String(t.id)) {
        li.style.fontWeight = 'bold';
      }
      li.href = `?type_id=${t.id}`; // чтобы url менялся
    //   li.onclick = (e) => {
    //     e.preventDefault();
    //     this.currentType = t.id;
    //     // Меняем url без перезагрузки
    //     window.history.pushState({}, '', `?type_id=${t.id}`);
    //     this.renderTypeList();
    //     this.renderTypeView();
    //   };
      list.appendChild(li);
    });
  }

  /**
   * Отображает подробную информацию о выбранном типе: название, действия, таблицу элементов и форму добавления.
   * Загружает элементы типа с сервера.
   * Также меняет title страницы на название типа.
   */
  async renderTypeView() {
    if (!this.currentType) {
      this.clearCurrentTypeView();
      return;
    }
    // Находим объект типа по id
    const typeObj = this.types.find(t => String(t.id) === String(this.currentType));
    if (!typeObj) {
      this.clearCurrentTypeView();
      return;
    }
    document.getElementById('typeName').textContent = typeObj.name;
    document.getElementById('typeActions').style.display = 'block';

    // Меняем title страницы на название типа
    document.title = typeObj.name;

    const res = await fetch(`/items/?type_id=${typeObj.id}`);
    const items = await res.json();
    this.renderItemsTable(items, typeObj);
    // Если фильтры открыты и инициализированы — подгрузим динамические по текущему типу
    if (window.filtersManager) {
      await window.filtersManager.setType(typeObj.id);
    }
    this.renderItemForm(typeObj);
  }

  /**
   * Отрисовывает таблицу элементов выбранного типа.
   * Если нет полей — показывает сообщение. Если нет данных — также сообщение.
   * В противном случае строит таблицу с данными.
   * @param {Array} items - Массив элементов для отображения
   * @param {Object} typeObj - Объект типа
   */
  renderItemsTable(items, typeObj) {
    const table = document.getElementById('itemsTable');
    if (!table) {
      console.error('Element с id "itemsTable" не найден.');
      return;
    }
    table.innerHTML = '';

    // Создаём thead и tbody
    const thead = document.createElement('thead');
    const tbody = document.createElement('tbody');

    if (!typeObj.fields || typeObj.fields.length === 0) {
      // Если нет полей, показываем сообщение в tbody
      const row = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 1;
      td.className = 'empty-message';
      td.textContent = 'Нет полей для отображения';
      row.appendChild(td);
      tbody.appendChild(row);
    } else {
      // Создаём заголовки
      const headerRow = document.createElement('tr');
      // Добавляем столбец "Название элемента" первым
      const thName = document.createElement('th');
      thName.textContent = 'Название элемента';
      thName.scope = "col";
      headerRow.appendChild(thName);
      console.log('создали название')

      typeObj.fields.forEach(f => {
        const th = document.createElement('th');
        th.textContent = f.name;
        th.scope = "col";
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);

      if (items.length === 0) {
        // Нет данных
        const row = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = typeObj.fields.length + 1; // +1 для названия
        td.className = 'empty-message';
        td.textContent = 'Нет данных';
        row.appendChild(td);
        tbody.appendChild(row);
      } else {
        // Данные
        items.forEach(item => {
          const row = document.createElement('tr');
          // Первый столбец — название элемента как ссылка на /items/<id>
          const tdName = document.createElement('td');
          if (item.id) {
            const a = document.createElement('a');
            a.href = `/item?item_id=${item.id}`;
            a.textContent = item.name ?? '-';
            a.style.textDecoration = 'none';
            a.style.color = '#0d6efd'; // Bootstrap primary
            tdName.appendChild(a);
          } else {
            tdName.textContent = item.name ?? '-';
          }
          row.appendChild(tdName);

          typeObj.fields.forEach(f => {
            const td = document.createElement('td');
            const v = (item.data && (item.data[f.id] ?? item.data[f.name])) ?? null;
            td.textContent = v !== null && v !== undefined && v !== '' ? v : '-';
            row.appendChild(td);
          });
          tbody.appendChild(row);
        });
      }
    }

    table.appendChild(thead);
    table.appendChild(tbody);
  }

  /**
   * Отрисовывает форму для добавления нового элемента выбранного типа в модальном окне.
   * Очищает базовые поля, добавляет динамические поля с отступами, обрабатывает отправку формы.
   * @param {Object} typeObj - Объект типа
   */
  renderItemForm(typeObj) {
    // Проверяем, что typeObj определён и является объектом
    if (!typeObj || typeof typeObj !== 'object') {
      console.error('typeObj не определён или не является объектом:', typeObj);
      return;
    }

    // Очищаем старую форму (если она есть)
    const form = document.getElementById('itemForm');
    if (form) {
      form.innerHTML = '';
    }

    // Находим модальное окно и форму для добавления вещества
    const addItemModal = document.getElementById('addItemModal');
    const addItemForm = document.getElementById('addItemForm');
    if (!addItemModal || !addItemForm) {
      console.error('Модальное окно или форма для добавления вещества не найдены.');
      return;
    }

    // Очищаем всю модалку: удаляем все дочерние элементы modal-body (все базовые поля)
    const modalBody = addItemForm.querySelector('.modal-body');
    if (modalBody) {
      modalBody.innerHTML = '';
    }

    // Создаём контейнер для динамических полей с отступами
    let dynamicFieldsContainer = modalBody ? modalBody.querySelector('.dynamic-fields-container') : null;
    if (!dynamicFieldsContainer && modalBody) {
      dynamicFieldsContainer = document.createElement('div');
      dynamicFieldsContainer.className = 'dynamic-fields-container px-3'; // px-3 — отступы слева и справа
      modalBody.appendChild(dynamicFieldsContainer);
    }
    if (dynamicFieldsContainer) {
      dynamicFieldsContainer.innerHTML = '';
    }

    // Добавляем поле для названия элемента (name) первым
    if (dynamicFieldsContainer) {
      const nameFieldWrapper = document.createElement('div');
      nameFieldWrapper.className = 'mb-3';
      const nameLabel = document.createElement('label');
      nameLabel.className = 'form-label';
      nameLabel.htmlFor = 'dynamicField_name';
      nameLabel.textContent = 'Название элемента *';
      const nameInput = document.createElement('input');
      nameInput.className = 'form-control';
      nameInput.type = 'text';
      nameInput.id = 'dynamicField_name';
      nameInput.name = 'name';
      nameInput.required = true;
      nameFieldWrapper.appendChild(nameLabel);
      nameFieldWrapper.appendChild(nameInput);
      dynamicFieldsContainer.appendChild(nameFieldWrapper);
    }

    // Проверяем, что поля существуют и это массив
    if (!Array.isArray(typeObj.fields) || typeObj.fields.length === 0) {
      if (dynamicFieldsContainer) {
        dynamicFieldsContainer.innerHTML += '<div class="empty-message">Добавьте поля для этого типа, чтобы вводить данные.</div>';
      }
      return;
    }

    // Для каждого поля создаём элементы с bootstrap-стилями, как в модальном окне
    typeObj.fields.forEach(f => {
      let fieldWrapper;
      let label;
      let input;

      if (f.field_type === 'bool') {
        // Чекбокс
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'form-check mt-3';

        input = document.createElement('input');
        input.className = 'form-check-input';
        input.type = 'checkbox';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        if (f.is_required) input.required = true;

        label = document.createElement('label');
        label.className = 'form-check-label';
        label.htmlFor = input.id;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        fieldWrapper.appendChild(input);
        fieldWrapper.appendChild(label);
      } else if (f.field_type === 'string') {
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'mb-3';

        label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `dynamicField_${f.name}`;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        input = document.createElement('input');
        input.className = 'form-control';
        input.type = 'text';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        input.placeholder = f.unit ? f.unit : '';
        if (f.is_required) input.required = true;

        fieldWrapper.appendChild(label);
        fieldWrapper.appendChild(input);
      } else if (f.field_type === 'int' || f.field_type === 'float') {
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'mb-3';

        label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `dynamicField_${f.name}`;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        input = document.createElement('input');
        input.className = 'form-control';
        input.type = 'number';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        input.placeholder = f.unit ? f.unit : '';
        if (f.field_type === 'float') input.step = 'any';
        if (f.is_required) input.required = true;

        fieldWrapper.appendChild(label);
        fieldWrapper.appendChild(input);
      } else if (f.field_type === 'date') {
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'mb-3';

        label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `dynamicField_${f.name}`;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        input = document.createElement('input');
        input.className = 'form-control';
        input.type = 'date';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        if (f.is_required) input.required = true;

        fieldWrapper.appendChild(label);
        fieldWrapper.appendChild(input);
      } else if (f.field_type === 'enum' && Array.isArray(f.choices)) {
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'mb-3';

        label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `dynamicField_${f.name}`;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        input = document.createElement('select');
        input.className = 'form-select';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        if (f.is_required) input.required = true;
        f.choices.forEach(choice => {
          const option = document.createElement('option');
          option.value = choice;
          option.textContent = choice;
          input.appendChild(option);
        });

        fieldWrapper.appendChild(label);
        fieldWrapper.appendChild(input);
      } else {
        // fallback
        fieldWrapper = document.createElement('div');
        fieldWrapper.className = 'mb-3';

        label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `dynamicField_${f.name}`;
        label.textContent = f.name + (f.unit ? ` (${f.unit})` : '') + (f.is_required ? ' *' : '');

        input = document.createElement('input');
        input.className = 'form-control';
        input.type = 'text';
        input.id = `dynamicField_${f.name}`;
        input.name = f.name;
        if (f.is_required) input.required = true;

        fieldWrapper.appendChild(label);
        fieldWrapper.appendChild(input);
      }

      if (dynamicFieldsContainer) {
        dynamicFieldsContainer.appendChild(fieldWrapper);
      }
    });

    // Обработка отправки формы (добавляем динамические поля в данные)
    addItemForm.onsubmit = async (e) => {
      e.preventDefault();
      // Собираем данные только из динамических полей
      const data = {};
      let nameValue = '';
      // Сначала получаем название элемента
      const nameInputEl = addItemForm.querySelector('[name="name"]');
      if (nameInputEl) {
        nameValue = nameInputEl.value;
      }
      for (const f of typeObj.fields) {
        const el = addItemForm.querySelector(`[name="${f.name}"]`);
        if (!el) continue;
        if (el.type === 'checkbox') {
          data[f.id] = el.checked;
        } else if (el.type === 'number') {
          data[f.id] = el.value === '' ? null : (el.step && el.step !== '1' ? parseFloat(el.value) : parseInt(el.value));
        } else {
          data[f.id] = el.value;
        }
      }

      await fetch('/items/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type_id: typeObj.id, name: nameValue, data })
      });
      // После добавления корректно скрываем модалку и убираем backdrop
      try {
        const modalInstance = (window.bootstrap && window.bootstrap.Modal)
          ? (window.bootstrap.Modal.getInstance(addItemModal) || new window.bootstrap.Modal(addItemModal))
          : null;
        if (modalInstance) {
          modalInstance.hide();
        } else if (typeof $ !== 'undefined' && $(addItemModal).modal) {
          $(addItemModal).modal('hide');
        } else {
          addItemModal.style.display = 'none';
        }
      } catch (_) {
        addItemModal.style.display = 'none';
      }
      document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      this.renderTypeView();
    //   ModalManager.renderFieldsList();
    
    };
  }

  /**
   * Возвращает тип input для поля по его типу (int, float, bool, date, string и т.д.).
   * @param {string} fieldType - Тип поля
   * @returns {string} - Тип input
   */
  getInputType(fieldType) {
    switch (fieldType) {
      case 'int':
      case 'float':
        return 'number';
      case 'bool':
        return 'checkbox';
      case 'date':
        return 'date';
      default:
        return 'text';
    }
  }

  /**
   * Собирает данные из формы в объект, учитывая типы input (checkbox, number и т.д.).
   * @param {HTMLFormElement} form - Форма для сбора данных
   * @returns {Object} - Собранные данные
   */
  collectFormData(form) {
    const data = {};
    for (const el of form.elements) {
      if (!el.name) continue;
      if (el.type === 'checkbox') {
        data[el.name] = el.checked;
      } else if (el.type === 'number') {
        data[el.name] = el.value === '' ? null : (el.step && el.step !== '1' ? parseFloat(el.value) : parseInt(el.value));
      } else {
        data[el.name] = el.value;
      }
    }
    return data;
  }

  /**
   * Очищает отображение текущего типа: сбрасывает название, скрывает действия, очищает форму и таблицу.
   */
  clearCurrentTypeView() {
    console.log('clearCurrentTypeView')
    document.getElementById('typeName').textContent = 'Выберите тип';
    document.getElementById('typeActions').style.display = 'none';
    document.getElementById('itemForm').innerHTML = '';
    document.getElementById('itemsTable').innerHTML = '';
    // Сбрасываем title страницы на дефолтный
    document.title = 'Справочник веществ';
  }
}


// ModalManager теперь учитывает, что currentType в TypeManager — это id типа, а не объект.
// Поэтому для получения объекта типа используется поиск по id в this.typeManager.types.

class ModalManager {
  constructor(typeManager) {
    this.typeManager = typeManager;
    this.editingFieldId = null;
    this.init();
  }

  init() {
    document.getElementById('newTypeForm').onsubmit = (e) => this.createType(e);
    document.getElementById('addFieldForm').onsubmit = (e) => this.addField(e);
  }

  showTypeModal() {
    document.getElementById('typeModal').style.display = 'flex';
    document.getElementById('newTypeForm').reset();
  }

  hideTypeModal() {
    document.getElementById('typeModal').style.display = 'none';
    // Корректно скрываем модалку и удаляем backdrop, если он остался
    const modalEl = document.getElementById('typeModal');
    if (window.bootstrap && window.bootstrap.Modal) {
      // Bootstrap 5
      const modalInstance = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
      modalInstance.hide();
    } else if (typeof $ !== 'undefined' && $(modalEl).modal) {
      // Bootstrap 4 или ниже (через jQuery)
      $(modalEl).modal('hide');
    } else {
      // Фоллбек — просто скрыть
      modalEl.style.display = 'none';
    }
    // Удаляем backdrop вручную, если он остался
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    // Убираем класс modal-open и сбрасываем overflow
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
  }

  async createType(e) {
    e.preventDefault();
    const name = e.target.name.value;

    // Добавляем стандартные поля для нового типа
    const defaultFields = [
      { name: 'Название', field_type: 'string', unit: null, is_required: true },
      { name: 'Описание', field_type: 'string', unit: null, is_required: false },
      { name: 'Дата создания', field_type: 'date', unit: null, is_required: true }
    ];

    // Создаём тип с этими полями
    const res = await fetch('/types/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, fields: defaultFields })
    });
    const newType = await res.json();
    this.typeManager.types.push(newType);
    this.hideTypeModal();
    this.typeManager.renderTypeList();
  }

  renderFieldsList() {
    const tbody = document.getElementById('fieldsList');
    if (!tbody) {
      console.error('Element с id "fieldsList" не найден.');
      return;
    }
    tbody.innerHTML = '';

    // Получаем id текущего типа
    const currentTypeId = this.typeManager.currentType;
    // Находим объект типа по id
    const typeObj = this.typeManager.types.find(t => String(t.id) === String(currentTypeId));

    if (!typeObj || !typeObj.fields || typeObj.fields.length === 0) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 5;
      td.className = 'text-center text-muted';
      td.textContent = 'Нет полей';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    typeObj.fields.forEach((f) => {
      const tr = document.createElement('tr');

      if (this.editingFieldId === f.id) {
        // Режим редактирования: инпуты
        const tdName = document.createElement('td');
        tdName.innerHTML = `<input id="edit_name_${f.id}" class="form-control form-control-sm" type="text" value="${f.name}">`;
        tr.appendChild(tdName);

        const tdType = document.createElement('td');
        const select = document.createElement('select');
        select.id = `edit_field_type_${f.id}`;
        select.className = 'form-select form-select-sm';
        ['string','int','float','bool','date','enum'].forEach(opt => {
          const o = document.createElement('option');
          o.value = opt; o.textContent = opt; if (opt === f.field_type) o.selected = true; select.appendChild(o);
        });
        tdType.appendChild(select);
        tr.appendChild(tdType);

        const tdUnit = document.createElement('td');
        tdUnit.innerHTML = `<input id="edit_unit_${f.id}" class="form-control form-control-sm" type="text" value="${f.unit || ''}">`;
        tr.appendChild(tdUnit);

        const tdRequired = document.createElement('td');
        tdRequired.innerHTML = `
          <div class="form-check">
            <input id="edit_is_required_${f.id}" class="form-check-input" type="checkbox" ${f.is_required ? 'checked' : ''}>
            <label class="form-check-label" for="edit_is_required_${f.id}">Да</label>
          </div>`;
        tr.appendChild(tdRequired);

        const tdActions = document.createElement('td');
        const saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'btn btn-sm btn-primary me-2';
        saveBtn.textContent = 'Сохранить';
        saveBtn.onclick = () => this.saveEditField(f.id);

        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-sm btn-secondary';
        cancelBtn.textContent = 'Отмена';
        cancelBtn.onclick = () => this.cancelEditField();

        tdActions.appendChild(saveBtn);
        tdActions.appendChild(cancelBtn);
        tr.appendChild(tdActions);
      } else {
        // Обычный режим: текст + действия
        const tdName = document.createElement('td');
        tdName.textContent = f.name;
        tr.appendChild(tdName);

        const tdType = document.createElement('td');
        tdType.textContent = f.field_type;
        tr.appendChild(tdType);

        const tdUnit = document.createElement('td');
        tdUnit.textContent = f.unit ? f.unit : '';
        tr.appendChild(tdUnit);

        const tdRequired = document.createElement('td');
        tdRequired.innerHTML = f.is_required ? '<span class="badge bg-success">Да</span>' : '<span class="badge bg-secondary">Нет</span>';
        tr.appendChild(tdRequired);

        const tdActions = document.createElement('td');
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn btn-sm btn-outline-primary me-2';
        editBtn.textContent = 'Изменить';
        editBtn.onclick = () => this.startEditField(f.id);

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'btn btn-sm btn-outline-danger';
        delBtn.textContent = 'Удалить';
        delBtn.onclick = () => this.deleteField(typeObj, f);

        tdActions.appendChild(editBtn);
        tdActions.appendChild(delBtn);
        tr.appendChild(tdActions);
      }

      tbody.appendChild(tr);
    });

    // Блокируем форму добавления, если редактируем поле
    const addFieldForm = document.getElementById('addFieldForm');
    if (addFieldForm) {
      const controls = addFieldForm.querySelectorAll('input, select, button');
      controls.forEach(el => { el.disabled = this.editingFieldId !== null; });
    }
  }

  startEditField(fieldId) {
    this.editingFieldId = fieldId;
    this.renderFieldsList();
  }

  cancelEditField() {
    this.editingFieldId = null;
    this.renderFieldsList();
  }

  async saveEditField(fieldId) {
    const currentTypeId = this.typeManager.currentType;
    const nameEl = document.getElementById(`edit_name_${fieldId}`);
    const typeEl = document.getElementById(`edit_field_type_${fieldId}`);
    const unitEl = document.getElementById(`edit_unit_${fieldId}`);
    const reqEl = document.getElementById(`edit_is_required_${fieldId}`);
    const payload = {
      name: nameEl ? nameEl.value.trim() : undefined,
      field_type: typeEl ? typeEl.value : undefined,
      unit: unitEl ? (unitEl.value.trim() || null) : undefined,
      is_required: reqEl ? !!reqEl.checked : undefined,
    };
    await fetch(`/types/${currentTypeId}/fields/${fieldId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    await this.typeManager.fetchTypes();
    this.editingFieldId = null;
    this.renderFieldsList();
    this.typeManager.renderTypeView();
  }

  async deleteField(typeObj, field) {
    const currentTypeId = this.typeManager.currentType;
    if (!confirm('Точно удалить поле? Это необратимо.')) return;
    await fetch(`/types/${currentTypeId}/fields/${field.id}`, { method: 'DELETE' });
    await this.typeManager.fetchTypes();
    this.renderFieldsList();
    this.typeManager.renderTypeView();
  }

  async addField(e) {
    e.preventDefault();
    const form = e.target;
    const name = form.name.value.trim();
    const field_type = form.field_type.value;
    const unit = form.unit.value.trim() || null;
    const is_required = form.is_required.checked;
    if (!name) return;

    // Получаем id текущего типа
    const currentTypeId = this.typeManager.currentType;
    if (!currentTypeId) {
      alert('Тип не выбран');
      return;
    }

    await fetch(`/types/${currentTypeId}/fields`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, field_type, unit, is_required })
    });
    await this.typeManager.fetchTypes();
    this.renderFieldsList();
    // Перерисовываем таблицу и форму, чтобы новое поле сразу появилось в UI
    this.typeManager.renderTypeView();
    // Сброс полей формы после успешного добавления
    try {
      form.reset();
      const nameInput = form.querySelector('[name="name"]');
      if (nameInput) nameInput.focus();
    } catch (_) {}
  }
}