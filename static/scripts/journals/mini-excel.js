class MiniExcel {
    constructor(containerElement, rows = null, cols = null) {
      console.log('нет таблицы');
      this.container = containerElement;
      this.table = containerElement.querySelector("table");
      this.data = {};
      this.currentInput = null;
      this.colorMap = {};

      if (!this.table) {
        this.rows = rows || 5;
        this.cols = cols || 5;
        this.colNames = Array.from({ length: this.cols }, (_, i) => this.numToCol(i));
        this.init();
        console.log('нет таблицы');
      } else {
        console.log('загружаем из существующей')
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

      this.attachListeners();
      this.setupResizeHandlers();
    }

    numToCol(num) {
      let col = '';
      while (num >= 0) {
        col = String.fromCharCode((num % 26) + 65) + col;
        num = Math.floor(num / 26) - 1;
      }
      return col;
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

        input.addEventListener("blur", () => {
          this.data[id] = input.value;
          // Сохраняем значение в data-value
          input.setAttribute('data-value', input.value);
          this.currentInput = null;
          this.recalculate();
          this.clearHighlights();
          this.togglePointerMode(false);
        });

        input.addEventListener("keydown", (e) => {
          if (e.key === "Enter") input.blur();
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

    getValue(id) {
      // Сначала пробуем взять из data, если нет — из data-value input
      let raw = this.data[id];
      if (raw === undefined) {
        const input = this.container.querySelector(`input[data-id="${id}"]`);
        if (input) {
          raw = input.getAttribute('data-value');
        }
      }
      if (!raw) return 0;

      if (raw.startsWith("=")) {
        try {
          const formula = raw.slice(1);
          if (formula.toUpperCase().startsWith("SUM(")) {
            const inside = formula.slice(4, -1);
            const refs = inside.split(",").flatMap(part =>
              part.includes(":") ? this.expandRange(part.trim()) : [part.trim()]
            );
            const values = refs.map(ref => parseFloat(this.getValue(ref)) || 0);
            return values.reduce((a, b) => a + b, 0);
          }

          const expr = formula.replace(/[A-Z][0-9]+/g, ref => {
            const val = this.getValue(ref);
            return isNaN(val) ? "0" : val;
          });
          return eval(expr);
        } catch {
          return "#ERR";
        }
      }

      return isNaN(raw) ? 0 : parseFloat(raw);
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

      inputs.forEach(input => {
        const id = input.dataset.id;
        const raw = this.data[id] !== undefined ? this.data[id] : input.getAttribute('data-value');

        if (raw?.startsWith("=")) {
          const result = this.getValue(id);
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

    loadFromExistingTable() {
      const tdElements = this.container.querySelectorAll("td[data-cell]");
      tdElements.forEach(td => {
        const id = td.dataset.cell;
        // Если есть input, берем значение из data-value, иначе из текста
        const input = td.querySelector('input');
        if (input) {
          // Если у input уже есть data-value, используем его, иначе берем из td
          let value = input.getAttribute('data-value');
          if (value === null) {
            value = td.textContent.trim();
            input.setAttribute('data-value', value);
          }
          input.value = value;
          this.data[id] = value;
        } else {
          this.data[id] = td.textContent.trim();
        }
      });

      this.attachListeners();
      this.setupResizeHandlers();
      this.recalculate();
    }
  }