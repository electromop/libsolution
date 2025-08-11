class MiniExcel {
    constructor(containerElement, rows = null, cols = null) {
      window.JLOG && JLOG('MiniExcel:ctor', { rows, cols });
      this.container = containerElement;
      this.table = containerElement.querySelector("table");
      this.data = {};
      this.colWidths = {}; // { "A": 90, "B": 120 }
      this.currentInput = null;
      this.colorMap = {};
      this.onChange = null;
      // Объединения ячеек
      this.merges = [];
      this.mergeAlias = new Map();
      this.mergeToolbar = null;

      if (!this.table) {
        this.rows = rows || 5;
        this.cols = cols || 5;
        this.colNames = Array.from({ length: this.cols }, (_, i) => this.numToCol(i));
        this.init();
        window.JLOG && JLOG('MiniExcel:init-new', { rows: this.rows, cols: this.cols });
      } else {
        window.JLOG && JLOG('MiniExcel:init-existing');
        this.loadFromExistingTable();
      }
    }

    init() {
      // Очистим контейнер
      this.container.innerHTML = "";

      const table = document.createElement("table");
      table.classList.add("mini-excel-table"); // Учитываем стили
      const thead = document.createElement("thead");
      const tbody = document.createElement("tbody");

      // Заголовки
      const headerRow = document.createElement("tr");
      headerRow.appendChild(document.createElement("th")); // Пустая ячейка
      this.colNames.forEach((col, i) => {
        const th = document.createElement("th");
        th.style.position = "relative"; // Для .col-resize
        th.innerHTML = `<b>${col}</b><div class="col-resize" data-col-index="${i}"></div>`;
        th.dataset.col = i;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      window.JLOG && JLOG('MiniExcel:init-start');
      // Построим карту объединений
      this._rebuildMergeMaps();

      // Ячейки
      for (let row = 1; row <= this.rows; row++) {
        const tr = document.createElement("tr");
        const th = document.createElement("th");
        th.textContent = row;
        tr.appendChild(th);
        for (let col = 0; col < this.cols; col++) {
          const cell = document.createElement("td");
          const cellId = `${this.colNames[col]}${row}`;
          cell.dataset.cell = cellId;
          // Пропустим покрытые ячейки (рисуем только master)
          const master = this.getMasterId(cellId);
          if (master !== cellId) {
            window.JLOG && JLOG('MiniExcel:covered-skip', { id: cellId, master });
            continue;
          }
          const span = this._getMergeSpan(cellId);
          if (span.colspan > 1) cell.colSpan = span.colspan;
          if (span.rowspan > 1) cell.rowSpan = span.rowspan;
          // Вставляем input в каждую ячейку
          const input = document.createElement("input");
          input.type = "text";
          input.dataset.id = cellId;
          input.id = cellId;
          // Сохраняем значение в data-value (если есть)
          if (this.data[cellId] !== undefined) {
            input.setAttribute('data-value', this.data[cellId]);
          }
          cell.appendChild(input);
          tr.appendChild(cell);
        }
        tbody.appendChild(tr);
      }

      table.appendChild(tbody);
      this.container.appendChild(table);
      this.table = table;
      window.JLOG && JLOG('MiniExcel:init-done');

      // Предзаполнить inputs значениями из this.data, чтобы сразу отрисовать корректно после recalculate
      this.populateFromData();

      this.attachListeners();
      this.setupResizeHandlers();
      this.applyColumnWidths();
      this._setupSelection();
      this.recalculate();
    }

    numToCol(num) {
      let col = '';
      while (num >= 0) {
        col = String.fromCharCode((num % 26) + 65) + col;
        num = Math.floor(num / 26) - 1;
      }
      return col;
    }

    colToNum(colStr) {
      // Convert A, B, ..., Z, AA, AB ... to 0-based index
      let n = 0;
      for (let i = 0; i < colStr.length; i++) {
        n = n * 26 + (colStr.charCodeAt(i) - 64);
      }
      return n - 1;
    }

    attachListeners() {
      // Используем this.container вместо this.root
      const inputs = this.container.querySelectorAll("input");

      inputs.forEach(input => {
        const id = input.dataset.id;

      input.addEventListener("focus", () => {
          // При фокусе берем значение из data-value, если оно есть
          input.value = input.getAttribute('data-value') ?? this.data[id] ?? "";
          this.currentInput = input;

          if (input.value.startsWith("=")) {
            this.highlightReferencedCells(input.value);
            this.togglePointerMode(true);
          }
        });

      input.addEventListener("keyup", () => {
        if (this.currentInput !== input) return;
        const val = input.value || "";
        // Подсветка ссылок во время набора формулы
        if (val.startsWith("=")) {
          this.highlightReferencedCells(val);
          this.togglePointerMode(true);
        } else {
          this.clearHighlights();
          this.togglePointerMode(false);
        }
      });

      // Сохранение по вводу (дебаунс)
      input.addEventListener("input", () => {
        this.data[id] = input.value;
        // не переписываем data-value мгновенно, обновим на blur
        this.recalculate();
        clearTimeout(this._inputTimer);
        this._inputTimer = setTimeout(() => {
          if (typeof this.onChange === 'function') {
            this.onChange();
          }
        }, 400);
      });

        input.addEventListener("blur", () => {
          this.data[id] = input.value;
          // Сохраняем значение в data-value
          input.setAttribute('data-value', input.value);
          this.currentInput = null;
          this.recalculate();
          this.clearHighlights();
          this.togglePointerMode(false);
          if (typeof this.onChange === 'function') {
            this.onChange();
          }
        });

        input.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            // По Enter при вводе формулы — подтвердим, пересчитаем и перейдем вниз
            this.data[id] = input.value;
            input.setAttribute('data-value', input.value);
            this.recalculate();
            if (typeof this.onChange === 'function') this.onChange();
            this.moveFocusDownFrom(input);
          }
        });

        input.addEventListener("mousedown", (e) => {
          if (this.currentInput && this.currentInput !== input) {
            const val = this.currentInput.value;
            if (val.startsWith("=")) {
              e.preventDefault();
              this.insertCellRef(input.dataset.id);
            }
          }
        });
      });
    }

    _createEvalContext() {
      return { cache: new Map(), visiting: new Set(), depth: 0, maxDepth: 64 };
    }

    getValue(id, ctx) {
      const context = ctx || this._createEvalContext();
      if (context.cache.has(id)) return context.cache.get(id);
      if (context.visiting.has(id)) return "#CYCLE";
      if (context.depth > context.maxDepth) return "#DEPTH";

      // Сначала пробуем взять из data, если нет — из data-value input
      let raw = this.data[id];
      if (raw === undefined) {
        const input = this.container.querySelector(`input[data-id="${id}"]`);
        if (input) raw = input.getAttribute('data-value');
      }
      if (!raw) {
        context.cache.set(id, 0);
        return 0;
      }

      if (raw.startsWith("=")) {
        try {
          context.visiting.add(id);
          context.depth += 1;
          const formula = raw.slice(1);
          if (formula.toUpperCase().startsWith("SUM(")) {
            const inside = formula.slice(4, -1);
            const refs = inside.split(",").flatMap(part =>
              part.includes(":") ? this.expandRange(part.trim()) : [part.trim()]
            );
            const values = refs.map(ref => parseFloat(this.getValue(ref, context)) || 0);
            const sum = values.reduce((a, b) => a + b, 0);
            context.visiting.delete(id);
            context.depth -= 1;
            context.cache.set(id, sum);
            return sum;
          }

          const expr = formula.replace(/[A-Z]+[0-9]+/g, ref => {
            const val = this.getValue(ref, context);
            return isNaN(val) ? "0" : val;
          });
          try {
            const safeEval = Function('"use strict"; return (' + expr + ');');
            const out = safeEval();
            context.visiting.delete(id);
            context.depth -= 1;
            context.cache.set(id, out);
            return out;
          } catch {
            context.visiting.delete(id);
            context.depth -= 1;
            context.cache.set(id, "#ERR");
            return "#ERR";
          }
        } catch {
          context.visiting.delete(id);
          context.depth -= 1;
          context.cache.set(id, "#ERR");
          return "#ERR";
        }
      }

      const num = isNaN(raw) ? 0 : parseFloat(raw);
      context.cache.set(id, num);
      return num;
    }

    expandRange(rangeStr) {
      const [start, end] = rangeStr.split(":");
      const parseCell = id => {
        const m = id.match(/^([A-Z]+)(\d+)$/);
        return [m[1], parseInt(m[2])];
      };

      const [startCol, startRow] = parseCell(start);
      const [endCol, endRow] = parseCell(end);

      const cols = this.colNames.filter(c => c >= startCol && c <= endCol);
      const rows = Array.from({ length: endRow - startRow + 1 }, (_, i) => i + startRow);

      return cols.flatMap(col => rows.map(row => `${col}${row}`));
    }

    recalculate() {
      // Используем this.container вместо this.root
      const inputs = this.container.querySelectorAll("input");

      const ctx = this._createEvalContext();
      inputs.forEach(input => {
        const id = input.dataset.id;
      const raw = this.data[id] !== undefined ? this.data[id] : input.getAttribute('data-value');

      // Не затираем текст в редактируемой ячейке, чтобы не мешать вводу формулы
      if (this.currentInput === input) return;

      if (raw?.startsWith("=")) {
        const result = this.getValue(id, ctx);
        input.value = result;
        input.style.background = "#f9f9f9";
      } else {
        input.value = raw || "";
        input.style.background = "#fff";
      }
      });
    }

    insertCellRef(refId) {
      const input = this.currentInput;
      const cursorPos = input.selectionStart || input.value.length;
      const before = input.value.slice(0, cursorPos);
      const after = input.value.slice(cursorPos);
      input.value = before + refId + after;

      setTimeout(() => {
        input.focus();
        input.setSelectionRange(cursorPos + refId.length, cursorPos + refId.length);
        this.highlightReferencedCells(input.value);
      }, 0);
    }

    ensureFocus() {
      // Вернуть фокус в активную ячейку или первую
      const active = this.container.querySelector('input:focus');
      const target = active || this.container.querySelector('input[data-id]');
      if (target) {
        target.focus();
        const len = target.value.length;
        try { target.setSelectionRange(len, len); } catch {}
      }
    }

    highlightReferencedCells(formula) {
      this.clearHighlights();
      this.colorMap = {};
      const refs = [...formula.matchAll(/[A-Z][0-9]+/g)].map(m => m[0]);

      // Используем this.container вместо this.root
      refs.forEach(ref => {
        const td = this.container.querySelector(`td[data-cell="${ref}"]`);
        if (td) td.style.backgroundColor = this.getRandomLightColor();
      });
    }

    clearHighlights() {
      // Используем this.container вместо this.root
      this.container.querySelectorAll("td").forEach(td => {
        td.style.backgroundColor = "";
      });
    }

    togglePointerMode(enable) {
      // Используем this.container вместо this.root
      this.container.querySelectorAll("td").forEach(td => {
        if (enable) {
          td.classList.add("pointer-mode");
        } else {
          td.classList.remove("pointer-mode");
        }
      });
    }

    setupResizeHandlers() {
      // Используем this.container вместо this.root
      const resizers = this.container.querySelectorAll('.col-resize');

      resizers.forEach(resizer => {
        let startX, startWidth, colIndex;

        resizer.addEventListener('mousedown', (e) => {
          startX = e.clientX;
          colIndex = parseInt(resizer.dataset.colIndex);
          const th = resizer.closest("th");
          startWidth = th.offsetWidth;

          const onMouseMove = (e) => {
            const delta = e.clientX - startX;
            const newWidth = Math.max(40, startWidth + delta) + 'px';

            this.container.querySelectorAll(`th[data-col="${colIndex}"]`).forEach(th => {
              th.style.width = newWidth;
            });

            const rows = this.container.querySelectorAll("tr");
            rows.forEach(row => {
              const cells = row.querySelectorAll("td");
              if (cells[colIndex]) {
                cells[colIndex].style.width = newWidth;
              }
            });
          };

          const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            // Зафиксируем ширину в colWidths
            const th = this.container.querySelector(`th[data-col="${colIndex}"]`);
            if (th) {
              const colName = this.colNames[colIndex];
              const numeric = parseInt(th.style.width || th.offsetWidth, 10);
              if (!isNaN(numeric)) {
                this.colWidths[colName] = numeric;
                if (typeof this.onChange === 'function') {
                  this.onChange();
                }
              }
            }
          };

          document.addEventListener('mousemove', onMouseMove);
          document.addEventListener('mouseup', onMouseUp);
        });
      });
    }

    getRandomLightColor() {
      const r = Math.floor(200 + Math.random() * 55);
      const g = Math.floor(200 + Math.random() * 55);
      const b = Math.floor(200 + Math.random() * 55);
      return `rgb(${r}, ${g}, ${b})`;
    }

    moveFocusDownFrom(input) {
      if (!input) return;
      const id = input.dataset.id; // e.g. A1
      const m = id && id.match(/^([A-Z]+)(\d+)$/);
      if (!m) return;
      const col = m[1];
      const row = parseInt(m[2], 10);
      const nextRow = row + 1;
      if (nextRow > this.rows) {
        this.addRow();
      }
      const nextId = `${col}${nextRow}`;
      const nextInput = this.container.querySelector(`input[data-id="${nextId}"]`);
      if (nextInput) {
        nextInput.focus();
        // Поместим курсор в конец
        const len = nextInput.value.length;
        nextInput.setSelectionRange(len, len);
      }
    }

    addRow() {
      this.rows += 1;
      this.init();
      if (typeof this.onChange === 'function') this.onChange();
    }

    addColumn() {
      this.cols += 1;
      this.colNames = Array.from({ length: this.cols }, (_, i) => this.numToCol(i));
      this.init();
      if (typeof this.onChange === 'function') this.onChange();
    }

    deleteRow(rowIndexOneBased) {
      const target = parseInt(rowIndexOneBased, 10);
      if (!Number.isInteger(target) || target < 1 || target > this.rows) return;
      if (this.rows <= 1) {
        // Минимум одна строка: просто очистим значения этой строки
        this.colNames.forEach(col => {
          const id = `${col}1`;
          delete this.data[id];
        });
        this.recalculate();
        if (typeof this.onChange === 'function') this.onChange();
        return;
      }
      const newData = {};
      Object.keys(this.data).forEach(key => {
        const m = key.match(/^([A-Z]+)(\d+)$/);
        if (!m) return;
        const col = m[1];
        const row = parseInt(m[2], 10);
        if (row < target) {
          newData[key] = this.data[key];
        } else if (row > target) {
          const newId = `${col}${row - 1}`;
          newData[newId] = this.data[key];
        }
        // row === target пропускаем (удаляем)
      });
      this.rows -= 1;
      this.data = newData;
      this.init();
      if (typeof this.onChange === 'function') this.onChange();
    }

    deleteColumn(colIndexOneBased) {
      const target = parseInt(colIndexOneBased, 10);
      if (!Number.isInteger(target) || target < 1 || target > this.cols) return;
      if (this.cols <= 1) {
        // Минимум одна колонка: просто очистим значения первого столбца
        for (let r = 1; r <= this.rows; r++) {
          const id = `${this.colNames[0]}${r}`;
          delete this.data[id];
        }
        this.recalculate();
        if (typeof this.onChange === 'function') this.onChange();
        return;
      }
      const newData = {};
      Object.keys(this.data).forEach(key => {
        const m = key.match(/^([A-Z]+)(\d+)$/);
        if (!m) return;
        const col = m[1];
        const row = parseInt(m[2], 10);
        const colIdx = this.colToNum(col) + 1; // to 1-based
        if (colIdx < target) {
          newData[key] = this.data[key];
        } else if (colIdx > target) {
          const newCol = this.numToCol(colIdx - 2); // shift left by 1 then 0-based
          const newId = `${newCol}${row}`;
          newData[newId] = this.data[key];
        }
        // colIdx === target пропускаем
      });
      this.cols -= 1;
      this.colNames = Array.from({ length: this.cols }, (_, i) => this.numToCol(i));
      this.data = newData;
      this.init();
      if (typeof this.onChange === 'function') this.onChange();
    }

    loadFromExistingTable() {
      // Если таблица уже существует — читаем data-value, чтобы заполнить this.data, затем пересчёт
      const tdElements = this.container.querySelectorAll("td[data-cell]");
      tdElements.forEach(td => {
        const id = td.dataset.cell;
        const input = td.querySelector('input');
        if (input) {
          const value = input.getAttribute('data-value');
          if (value !== null) {
            this.data[id] = value;
          }
        }
      });

      this.attachListeners();
      this.setupResizeHandlers();
      this.applyColumnWidths();
      // Вызовем пересчёт, чтобы формулы отобразились без кликов
      this.recalculate();
    }

    populateFromData() {
      if (!this.data) return;
      const inputs = this.container.querySelectorAll('input[data-id]');
      inputs.forEach(input => {
        const id = input.getAttribute('data-id');
        if (id && this.data[id] !== undefined) {
          input.setAttribute('data-value', this.data[id]);
        }
      });
    }

    applyColumnWidths() {
      const headerCells = this.container.querySelectorAll('thead th[data-col]');
      headerCells.forEach(th => {
        const colIndex = parseInt(th.getAttribute('data-col'), 10);
        const colName = this.colNames[colIndex];
        const width = this.colWidths[colName];
        if (width) {
          th.style.width = `${width}px`;
          const rows = this.container.querySelectorAll('tbody tr');
          rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells[colIndex]) {
              cells[colIndex].style.width = `${width}px`;
              const input = cells[colIndex].querySelector('input');
              if (input) input.style.width = `${Math.max(20, width - 16)}px`;
            }
          });
        }
      });
    }

    export() {
      return {
        rows: this.rows,
        cols: this.cols,
        data: { ...this.data },
        colWidths: { ...this.colWidths },
        merges: Array.isArray(this.merges) ? [...this.merges] : [],
      };
    }

    import(tableObj) {
      if (!tableObj) return;
      const { rows, cols, data, colWidths, merges } = tableObj;
      if (Number.isInteger(rows) && Number.isInteger(cols)) {
        this.rows = rows;
        this.cols = cols;
        this.colNames = Array.from({ length: this.cols }, (_, i) => this.numToCol(i));
        this.data = data || {};
        this.colWidths = colWidths || {};
        this.merges = Array.isArray(merges) ? merges : [];
        this.init();
      } else {
        this.data = data || {};
        this.colWidths = colWidths || {};
        this.merges = Array.isArray(merges) ? merges : [];
        this.applyColumnWidths();
        this.recalculate();
      }
    }

    _setupSelection() {
      this.isSelecting = false;
      this.selStart = null;
      this.selEnd = null;
      const onMouseDown = (e) => {
        const td = e.target.closest('td[data-cell]');
        if (!td) return;
        const id = td.dataset.cell;
        this.isSelecting = true;
        this.selStart = id;
        this.selEnd = id;
        this._renderSelection();
      };
      const onMouseMove = (e) => {
        if (!this.isSelecting) return;
        const td = e.target.closest('td[data-cell]');
        if (!td) return;
        const id = td.dataset.cell;
        if (id !== this.selEnd) {
          this.selEnd = id;
          this._renderSelection();
        }
      };
      const onMouseUp = () => {
        if (!this.isSelecting) return;
        this.isSelecting = false;
        this._renderSelection(true);
      };
      this.container.addEventListener('mousedown', onMouseDown);
      this.container.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    }

    _getSelRect() {
      if (!this.selStart || !this.selEnd) return null;
      const a = this._idToCoord(this.getMasterId(this.selStart));
      const b = this._idToCoord(this.getMasterId(this.selEnd));
      if (!a || !b) return null;
      const left = Math.min(a.colIdx, b.colIdx);
      const right = Math.max(a.colIdx, b.colIdx);
      const top = Math.min(a.row, b.row);
      const bottom = Math.max(a.row, b.row);
      return { left, right, top, bottom };
    }

    _renderSelection(showToolbar = false) {
      this.container.querySelectorAll('td[data-cell]').forEach(td => td.classList.remove('mx-selected'));
      const rect = this._getSelRect();
      if (!rect) { if (this._hideMergeToolbar) this._hideMergeToolbar(); return; }
      for (let r = rect.top; r <= rect.bottom; r++) {
        for (let c = rect.left; c <= rect.right; c++) {
          const id = this._coordToId(c, r);
          const td = this.container.querySelector(`td[data-cell="${id}"]`);
          if (td) td.classList.add('mx-selected');
        }
      }
      if (showToolbar && this._positionMergeToolbar) this._positionMergeToolbar(rect);
    }

    _ensureMergeToolbar() { /* Панель отключена: используем тулбар страницы */ }
    _hideMergeToolbar() { /* noop */ }
    _positionMergeToolbar() { /* noop */ }

    mergeSelection() {
      const rect = this._getSelRect();
      if (!rect) return;
      const area = (rect.right - rect.left + 1) * (rect.bottom - rect.top + 1);
      if (area <= 1) return;
      const start = this._coordToId(rect.left, rect.top);
      const end = this._coordToId(rect.right, rect.bottom);
      for (let r = rect.top; r <= rect.bottom; r++) {
        for (let c = rect.left; c <= rect.right; c++) {
          const id = this._coordToId(c, r);
          if (id !== start) delete this.data[id];
        }
      }
      this.merges.push({ start, end });
      this.init();
      if (typeof this.onChange === 'function') this.onChange();
    }

    unmergeSelection() {
      const rect = this._getSelRect();
      if (!rect) return;
      const inside = (mg) => {
        const a = this._idToCoord(mg.start);
        const b = this._idToCoord(mg.end);
        const left = Math.min(a.colIdx, b.colIdx);
        const right = Math.max(a.colIdx, b.colIdx);
        const top = Math.min(a.row, b.row);
        const bottom = Math.max(a.row, b.row);
        return left >= rect.left && right <= rect.right && top >= rect.top && bottom <= rect.bottom;
      };
      const idx = Array.isArray(this.merges) ? this.merges.findIndex(mg => inside(mg)) : -1;
      if (idx >= 0) {
        this.merges.splice(idx, 1);
        this.init();
        if (typeof this.onChange === 'function') this.onChange();
      }
    }

    // --- Merge helpers ---
    _idToCoord(id) {
      const m = id.match(/^([A-Z]+)(\d+)$/);
      if (!m) return null;
      return { colName: m[1], colIdx: this.colToNum(m[1]) + 1, row: parseInt(m[2], 10) };
    }

    _coordToId(colIdxOneBased, row) {
      return `${this.numToCol(colIdxOneBased - 1)}${row}`;
    }

    _rebuildMergeMaps() {
      this.mergeAlias = new Map();
      if (!Array.isArray(this.merges)) this.merges = [];
      this.merges.forEach(mg => {
        const a = this._idToCoord(mg.start);
        const b = this._idToCoord(mg.end);
        if (!a || !b) return;
        const left = Math.min(a.colIdx, b.colIdx);
        const right = Math.max(a.colIdx, b.colIdx);
        const top = Math.min(a.row, b.row);
        const bottom = Math.max(a.row, b.row);
        const masterId = this._coordToId(left, top);
        for (let r = top; r <= bottom; r++) {
          for (let c = left; c <= right; c++) {
            const id = this._coordToId(c, r);
            if (id !== masterId) this.mergeAlias.set(id, masterId);
          }
        }
      });
    }

    getMasterId(id) {
      return this.mergeAlias.get(id) || id;
    }

    _getMergeSpan(id) {
      let colspan = 1, rowspan = 1;
      const mg = Array.isArray(this.merges) && this.merges.find(m => {
        const a = this._idToCoord(m.start);
        const b = this._idToCoord(m.end);
        if (!a || !b) return false;
        const left = Math.min(a.colIdx, b.colIdx);
        const top = Math.min(a.row, b.row);
        return this._coordToId(left, top) === id;
      });
      if (mg) {
        const a = this._idToCoord(mg.start);
        const b = this._idToCoord(mg.end);
        colspan = Math.abs(a.colIdx - b.colIdx) + 1;
        rowspan = Math.abs(a.row - b.row) + 1;
      }
      return { colspan, rowspan };
    }
  }