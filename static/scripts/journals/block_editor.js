// --- block_editor.js ---
// Простейший блочный редактор. Каждый параграф/таблица/и т.д. хранится как отдельный div.
// Пока поддерживается только текстовый параграф (paragraph).
// В дальнейшем можно расширить поддержкой таблиц, изображений, дат и т.д.

class BlockEditorManager {
    constructor(containerId, onBlockInput, onBlockCreate, onBlockDelete, onBlockReorder) {
        this.container = document.getElementById(containerId);
        this.onBlockInput = onBlockInput; // callback(blockId, html)
        this.onBlockCreate = onBlockCreate; // callback(afterBlockId, tempId)
        this.onBlockDelete = onBlockDelete; // callback(blockId)
        this.onBlockReorder = onBlockReorder; // callback(orderIds: string[])
        this.dragSrcEl = null;
    }

    clear() {
        this.container.innerHTML = "";
    }

    renderBlocks(blocks) {
        this.clear();
        if (!blocks || blocks.length === 0) {
            // Если блоков нет – создаём пустой параграф, который пока не сохранён на сервере
            this._createBlockElement("tmp-" + Date.now(), "paragraph", "<p><br/></p>");
            return;
        }
        blocks.sort((a, b) => a.position - b.position);
        for (const blk of blocks) {
            this._createBlockElement(blk.id, blk.block_type, blk.html, blk.table);
        }
    }

    updateBlock(blockId, html, table) {
        const el = this.container.querySelector(`[data-block-id="${blockId}"]`);
        if (!el) return;
        const cont = el.querySelector('.block-content');
        if (!cont) return;
        const type = el.getAttribute('data-block-type') || 'paragraph';
        if (type === 'table') {
            // Игнорируем html, всегда пересобираем по JSON
            cont.innerHTML = "";
            const wrapper = document.createElement('div');
            wrapper.className = 'mini-excel-container';
            const tableRoot = document.createElement('div');
            tableRoot.className = 'mini-excel-root';
            wrapper.appendChild(tableRoot);
            cont.appendChild(wrapper);
            const excel = new MiniExcel(tableRoot, (table?.rows) || 10, (table?.cols) || 5);
            if (table) excel.import(table);
            // После импорта сразу пересчитать, чтобы формулы показались
            excel.recalculate();
            // Экспортируем инстанс для тулбара (merge/unmerge)
            wrapper.__excel = excel;
            tableRoot.__excel = excel;
            const setActive = () => { window.activeExcel = excel; };
            wrapper.addEventListener('focusin', setActive);
            tableRoot.addEventListener('focusin', setActive);
            wrapper.addEventListener('mousedown', setActive);
            tableRoot.addEventListener('mousedown', setActive);
            excel.onChange = () => {
                const currentId = el.getAttribute("data-block-id");
                const serialized = excel.export();
                const payload = { html: cont.innerHTML, table: serialized };
                if (typeof this.onBlockInput === 'function') this.onBlockInput(currentId, payload);
            };
            // Прокрутка к таблице на всякий случай
            setTimeout(() => {
                wrapper.scrollIntoView({ behavior: 'instant', block: 'nearest' });
            }, 0);
        } else if (type === 'image') {
            cont.innerHTML = html || '';
            cont.style.position = 'relative';
            this._attachImageControls(el, cont);
        } else if (cont && cont.innerHTML !== html) {
            cont.innerHTML = html;
        }
    }

    // Добавить новые блоки без очистки (например, при подгрузке)
    _generateTempId() {
        return "tmp-" + Math.random().toString(36).slice(2);
    }

    assignRealId(tempId, realId) {
        const el = this.container.querySelector(`[data-block-id="${tempId}"]`);
        if (el) {
            el.setAttribute("data-block-id", realId);
        }
    }

    addBlocks(blocks) {
        if (!blocks || blocks.length === 0) return;
        blocks.sort((a, b) => a.position - b.position);
        for (const blk of blocks) {
            if (!this.container.querySelector(`[data-block-id="${blk.id}"]`)) {
                this._createBlockElement(blk.id, blk.block_type, blk.html, blk.table);
            }
        }
    }

    _createBlockElement(id, type, html, table) {
        const debounce = (fn, delay = 300) => {
            let timer;
            return function (...args) {
                clearTimeout(timer);
                timer = setTimeout(() => fn.apply(this, args), delay);
            };
        };
        const tempId = id || this._generateTempId();
        const div = document.createElement("div");
        div.classList.add("editor-block");
        if (type) div.setAttribute('data-block-type', type);
        // --- drag handle ---
        const handle = document.createElement("span");
        handle.classList.add("drag-handle");
        handle.textContent = "⠿";
        handle.setAttribute("contenteditable", "false");
        div.setAttribute("data-block-id", tempId);
        // Контейнер содержимого
        const content = document.createElement("div");
        content.classList.add("block-content");
        // TABLE-блоки не должны быть редактируемыми как текст (внутри собственные input'ы)
        if (type === 'table') {
            content.contentEditable = false;
            // Создаём/восстанавливаем MiniExcel в отдельном корне, чтобы не затирать кнопки
            const wrapper = document.createElement('div');
            wrapper.className = 'mini-excel-container';
            const tableRoot = document.createElement('div');
            tableRoot.className = 'mini-excel-root';
            wrapper.appendChild(tableRoot);
            content.appendChild(wrapper);
            const addRowBtn = document.createElement('button');
            addRowBtn.type = 'button';
            addRowBtn.className = 'mini-excel-plus mini-excel-add-row';
            addRowBtn.textContent = '+';
            const addColBtn = document.createElement('button');
            addColBtn.type = 'button';
            addColBtn.className = 'mini-excel-plus mini-excel-add-col';
            addColBtn.textContent = '+';
            const delRowBtn = document.createElement('button');
            delRowBtn.type = 'button';
            delRowBtn.className = 'mini-excel-del-row';
            delRowBtn.textContent = '–';
            addRowBtn.style.display = 'none';
            addColBtn.style.display = 'none';
            delRowBtn.style.display = 'none';
            wrapper.appendChild(addRowBtn);
            wrapper.appendChild(addColBtn);
            wrapper.appendChild(delRowBtn);

            window.JLOG && JLOG('BlockEditor:create-table', { id: tempId });
            const excel = new MiniExcel(tableRoot, (table?.rows) || 10, (table?.cols) || 5);
            window.JLOG && JLOG('BlockEditor:excel-created', { id: tempId, rows: table?.rows, cols: table?.cols });
            // Экспонируем экземпляр для внешних действий (merge из тулбара)
            wrapper.__excel = excel;
            tableRoot.__excel = excel;
            // Запоминаем активную таблицу только по фокусу/взаимодействию, НЕ по hover
            const setActive = () => { window.activeExcel = excel; window.JLOG && JLOG('ActiveExcel:set', {}); };
            wrapper.addEventListener('focusin', setActive);
            tableRoot.addEventListener('focusin', setActive);
            wrapper.addEventListener('mousedown', setActive);
            tableRoot.addEventListener('mousedown', setActive);
            // Рисуем таблицу ТОЛЬКО из JSON
            excel.import(table || { rows: 10, cols: 5, data: {}, colWidths: {} });
            // Подписка на изменения
            excel.onChange = () => {
                window.JLOG && JLOG('BlockEditor:excel-change', { id: tempId });
                const currentId = div.getAttribute("data-block-id");
                const serialized = excel.export();
                const payload = {
                    html: content.innerHTML,
                    table: serialized,
                };
                if (typeof this.onBlockInput === 'function') {
                    this.onBlockInput(currentId, payload);
                }
            };
            // Вспомогательные: показать/скрыть кнопки при работе с таблицей
            const showControls = () => {
                addRowBtn.style.display = '';
                addColBtn.style.display = '';
                delRowBtn.style.display = '';
                delColBtn.style.display = '';
            };
            const hideControls = () => {
                addRowBtn.style.display = 'none';
                addColBtn.style.display = 'none';
                delRowBtn.style.display = 'none';
                delColBtn.style.display = 'none';
            };
            wrapper.addEventListener('focusin', showControls);
            // Подсказки показываем по наведению, но активную таблицу НЕ меняем по hover
            wrapper.addEventListener('focusout', (e) => {
                // Подождём, вдруг фокус уйдёт на другой input внутри wrapper
                setTimeout(() => {
                    if (!wrapper.contains(document.activeElement)) hideControls();
                }, 0);
            });
            wrapper.addEventListener('mouseover', showControls);
            wrapper.addEventListener('mouseout', () => {
                if (!wrapper.contains(document.activeElement)) hideControls();
            });
            // Дублируем обработчики на корень таблицы, чтобы точно ловить события
            tableRoot.addEventListener('mouseover', showControls);
            tableRoot.addEventListener('mouseout', () => {
                if (!wrapper.contains(document.activeElement)) hideControls();
            });

            addRowBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                excel.addRow();
                this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn);
                if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
            });
            addColBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                excel.addColumn();
                this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn);
                if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
            });
            delRowBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                // Определяем текущую строку по фокусу, иначе по наведению (если курсор над строкой)
                const active = wrapper.querySelector('input:focus');
                let row = null;
                if (active) {
                    const m = active.dataset.id && active.dataset.id.match(/^([A-Z]+)(\d+)$/);
                    row = m ? parseInt(m[2], 10) : null;
                }
                if (!row) {
                    // Попытаемся определить по последнему td:hover
                    const hovered = wrapper.querySelector('td:hover input');
                    if (hovered) {
                        const m = hovered.dataset.id && hovered.dataset.id.match(/^([A-Z]+)(\d+)$/);
                        row = m ? parseInt(m[2], 10) : null;
                    }
                }
                excel.deleteRow(row || excel.rows);
                this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn, delRowBtn, delColBtn);
                if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
            });

            // Удаление колонки: кнопка справа по центру
            const delColBtn = document.createElement('button');
            delColBtn.type = 'button';
            delColBtn.className = 'mini-excel-del-row'; // такой же стиль, но позиция иная
            delColBtn.textContent = '–';
            delColBtn.style.display = 'none';
            wrapper.appendChild(delColBtn);
            delColBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                const active = wrapper.querySelector('input:focus');
                let colIdx = null;
                if (active) {
                    const m = active.dataset.id && active.dataset.id.match(/^([A-Z]+)(\d+)$/);
                    if (m) {
                        colIdx = excel.colToNum(m[1]) + 1;
                    }
                }
                if (!colIdx) {
                    // По наведению на td
                    const hovered = wrapper.querySelector('td:hover input');
                    if (hovered) {
                        const m = hovered.dataset.id && hovered.dataset.id.match(/^([A-Z]+)(\d+)$/);
                        if (m) colIdx = excel.colToNum(m[1]) + 1;
                    }
                }
                excel.deleteColumn(colIdx || excel.cols);
                this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn, delRowBtn, delColBtn);
                if (typeof excel.ensureFocus === 'function') excel.ensureFocus();
            });

            // Первичное позиционирование плюсиков у границ таблицы
            setTimeout(() => this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn, delRowBtn, delColBtn), 0);
            const ro = new ResizeObserver(() => this._positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn, delRowBtn, delColBtn));
            ro.observe(tableRoot);
        } else if (type === 'image') {
            content.contentEditable = false;
            content.innerHTML = html || '';
            content.style.position = 'relative';
            this._attachImageControls(div, content);
        } else {
            content.contentEditable = true;
            content.innerHTML = html || "";
        }
        div.appendChild(handle);
        div.appendChild(content);

        // Событие ввода: уведомляем менеджер WS
        // Shift+Enter – создать новый блок ниже (обычный Enter делает перенос строки)
        content.addEventListener("keydown", (e) => {
            // Удаление блока если пуст и Backspace
            if (e.key === "Backspace" && content.innerText.trim() === "") {
                e.preventDefault();
                const prev = div.previousElementSibling;
                const blockIdDel = div.getAttribute("data-block-id");
                if (prev) {
                    const pc = prev.querySelector('.block-content');
                    if (pc) {
                        pc.focus();
                        try {
                            const range = document.createRange();
                            range.selectNodeContents(pc);
                            range.collapse(false); // в конец
                            const sel = window.getSelection();
                            sel.removeAllRanges();
                            sel.addRange(range);
                        } catch (_) {}
                    }
                }
                div.remove();
                if (typeof this.onBlockDelete === "function") {
                    this.onBlockDelete(blockIdDel);
                }
                return;
            }
            if (type !== 'table' && type !== 'image' && e.key === "Enter" && e.shiftKey) {
                e.preventDefault();
                const newTempId = this._createBlockElement(null, "paragraph", "<p><br/></p>");
                // Перемещаем только что созданный блок сразу после текущего
                const newEl = this.container.querySelector(`[data-block-id="${newTempId}"]`);
                if (newEl) {
                    this.container.insertBefore(newEl, div.nextSibling);
                    // Фокусируем курсор в новый блок
                    setTimeout(() => {
                        const cont = newEl.querySelector('.block-content');
                        if (cont) cont.focus();
                    }, 0);
                }
                if (typeof this.onBlockCreate === "function") {
                    const afterRealId = div.getAttribute("data-block-id");
                    this.onBlockCreate(afterRealId, newTempId);
                }
            }
        });

        if (type !== 'table' && type !== 'image') {
            const debouncedInput = debounce(() => {
                if (typeof this.onBlockInput === "function") {
                    const currentId = div.getAttribute("data-block-id");
                    this.onBlockInput(currentId, content.innerHTML);
                }
            }, 400);
            content.addEventListener("input", debouncedInput);
            // При фокусе на другой блок — сбрасываем фокус таблицы
            content.addEventListener('focusin', () => {
                if (window.activeExcel) {
                    const focused = document.querySelector('#editor .mini-excel-root input:focus');
                    if (focused) focused.blur();
                    window.activeExcel = null;
                }
            });
        }

        // --- Drag & drop ---
        div.draggable = false; // по умолчанию блок не перетаскивается
        handle.draggable = true;

        handle.addEventListener("dragstart", (e) => {
            div.classList.add("dragging");
            this.dragSrcEl = div;
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", "");
        });
        handle.addEventListener("dragend", () => {
            div.classList.remove("dragging");
            clearDragOver();
        });
        div.addEventListener("dragstart", (e) => {
            this.dragSrcEl = div;
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", "");
        });
        const clearDragOver = () => {
            this.container.querySelectorAll(".drag-over").forEach(el => el.classList.remove("drag-over"));
        };

        div.addEventListener("dragover", (e) => {
            e.preventDefault();
            if (this.dragSrcEl === div) return;
            e.dataTransfer.dropEffect = "move";
            clearDragOver();
            div.classList.add("drag-over");
        });
        div.addEventListener("drop", (e) => {
            e.preventDefault();
            clearDragOver();
            if (this.dragSrcEl && this.dragSrcEl !== div) {
                // Перемещаем элемент в DOM
                const blocks = Array.from(this.container.children);
                const srcIndex = blocks.indexOf(this.dragSrcEl);
                const destIndex = blocks.indexOf(div);
                if (srcIndex < destIndex) {
                    this.container.insertBefore(this.dragSrcEl, div.nextSibling);
                } else {
                    this.container.insertBefore(this.dragSrcEl, div);
                }
                // Отправляем новый порядок блоков (только реальные id)
                const order = Array.from(this.container.querySelectorAll('.editor-block'))
                  .map(el => el.getAttribute('data-block-id'))
                  .filter(id => id && !id.startsWith('tmp-'));
                if (typeof this.onBlockReorder === 'function') {
                    this.onBlockReorder(order);
                }
            }
        });

        this.container.appendChild(div);
        return tempId;
    }

    _attachImageControls(wrapper, content) {
        try {
            // Не дублировать
            if (content.querySelector('.image-actions')) return;
            const blockId = wrapper.getAttribute('data-block-id');
            const actions = document.createElement('div');
            actions.className = 'image-actions';
            actions.style.position = 'absolute';
            actions.style.top = '8px';
            actions.style.right = '8px';
            actions.style.display = 'flex';
            actions.style.gap = '6px';
            actions.style.zIndex = '2';

            const changeBtn = document.createElement('button');
            changeBtn.type = 'button';
            changeBtn.textContent = 'Изм.';
            changeBtn.className = 'btn btn-sm btn-primary';
            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.textContent = 'Удалить';
            delBtn.className = 'btn btn-sm btn-outline-danger';

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.style.display = 'none';

            actions.appendChild(changeBtn);
            actions.appendChild(delBtn);
            content.appendChild(actions);
            content.appendChild(fileInput);

            // Поменять фото: загрузим в бекэнд и отправим image_url через WS
            changeBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
            fileInput.addEventListener('change', () => {
                const f = fileInput.files && fileInput.files[0];
                if (!f) return;
                // Локальное превью
                const reader = new FileReader();
                reader.onload = () => {
                    const img = content.querySelector('img');
                    if (img) {
                        img.src = reader.result;
                    }
                };
                reader.readAsDataURL(f);
                // Загрузка в бекэнд
                const m = window.location.pathname.match(/\/journal\/(\d+)/);
                const journalId = m ? m[1] : null;
                if (!journalId) return;
                const form = new FormData();
                form.append('file', f);
                fetch(`/api/journals/${journalId}/upload_image`, { method: 'POST', body: form })
                  .then(r => r.json())
                  .then(data => {
                      if (data && data.url && typeof window.wsBlocks?.sendBlockUpdate === 'function') {
                          window.wsBlocks.sendBlockUpdate(blockId, { image_url: data.url });
                      }
                  })
                  .catch(() => {});
            });

            // Удалить блок
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!confirm('Удалить блок изображения?')) return;
                if (typeof this.onBlockDelete === 'function') {
                    this.onBlockDelete(blockId);
                }
                wrapper.remove();
            });
        } catch (_) {}
    }

    // Установить порядок блоков согласно списку id
    reorderBlocks(orderIds) {
        if (!Array.isArray(orderIds) || orderIds.length === 0) return;
        const idToEl = {};
        this.container.querySelectorAll('.editor-block').forEach(el => {
            const id = el.getAttribute('data-block-id');
            if (id) idToEl[id] = el;
        });
        let last = null;
        orderIds.forEach(id => {
            const el = idToEl[id];
            if (el) {
                if (last) {
                    this.container.insertBefore(el, last.nextSibling);
                } else {
                    this.container.insertBefore(el, this.container.firstChild);
                }
                last = el;
            }
        });
    }

    _positionTablePlusButtons(wrapper, tableRoot, addRowBtn, addColBtn, delRowBtn, delColBtn) {
        if (!wrapper || !tableRoot || !addRowBtn || !addColBtn) return;
        const tableEl = tableRoot.querySelector('table');
        if (!tableEl) return;
        const rect = tableEl.getBoundingClientRect();
        const contRect = wrapper.getBoundingClientRect();
        // Позиционируем относительно контейнера wrapper
        const offsetLeft = rect.left - contRect.left;
        const offsetTop = rect.top - contRect.top;

        // Кнопка строки: прижата по нижней кромке таблицы слева
        addRowBtn.style.left = `${Math.max(0, offsetLeft)}px`;
        addRowBtn.style.top = `${offsetTop + rect.height - addRowBtn.offsetHeight / 2}px`;

        // Кнопка колонки: прижата по правой кромке таблицы сверху
        addColBtn.style.left = `${offsetLeft + rect.width - addColBtn.offsetWidth / 2}px`;
        addColBtn.style.top = `${Math.max(0, offsetTop)}px`;

        if (delRowBtn) {
            // Кнопка удаления строки: снизу справа
            delRowBtn.style.left = `${offsetLeft + rect.width - delRowBtn.offsetWidth / 2}px`;
            delRowBtn.style.top = `${offsetTop + rect.height - delRowBtn.offsetHeight / 2}px`;
        }
        if (delColBtn) {
            // Кнопка удаления колонки: справа по центру
            delColBtn.style.left = `${offsetLeft + rect.width - delColBtn.offsetWidth / 2}px`;
            delColBtn.style.top = `${offsetTop + rect.height / 2 - delColBtn.offsetHeight / 2}px`;
        }
    }
}
