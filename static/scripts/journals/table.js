class MiniExcel {
    constructor(containerOrId, rows = 10, cols = 5) {
      this.container = typeof containerOrId === 'string' ? document.getElementById(containerOrId) : containerOrId;
      this.rows = rows;
      this.cols = cols;
      this.data = {};
      this.colWidths = {};
      this.colNames = Array.from({ length: cols }, (_, i) => String.fromCharCode(65 + i));
      this.currentInput = null;
      this.onChange = null;
      this.init();
    }

    init() {
      this.container.innerHTML = '';
      const table = document.createElement('table');
      const headerRow = document.createElement('tr');
      headerRow.innerHTML = `<th></th>` + this.colNames.map(c => `<th data-col="${c}"><b>${c}</b></th>`).join('');
      table.appendChild(headerRow);

      for (let r = 1; r <= this.rows; r++) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<th><b>${r}</b></th>` + this.colNames.map(col => {
          const id = `${col}${r}`;
          return `<td data-cell="${id}"><input data-id="${id}" id="${id}" /></td>`;
        }).join('');
        table.appendChild(tr);
      }

      this.container.appendChild(table);
      this.applyColumnWidths();
      this.attachListeners();
      this.recalculate();
    }

    attachListeners() {
      const inputs = this.container.querySelectorAll("input");

      inputs.forEach(input => {
        const id = input.dataset.id;

        input.addEventListener("focus", () => {
          input.value = this.data[id] || "";
          this.currentInput = input;

          // Подсветка формульных ссылок
          if (input.value.startsWith("=")) {
            this.highlightReferencedCells(input.value);
            this.togglePointerMode(true);
          }
        });

        input.addEventListener("blur", () => {
          this.data[id] = input.value;
          this.currentInput = null;
          this.recalculate();
          this.clearHighlights();
          this.togglePointerMode(false);
          if (typeof this.onChange === 'function') {
            this.onChange();
          }
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

    applyColumnWidths() {
      const table = this.container.querySelector('table');
      if (!table) return;
      const headerCells = table.querySelectorAll('th[data-col]');
      headerCells.forEach(th => {
        const colName = th.getAttribute('data-col');
        const width = this.colWidths[colName];
        if (width) {
          th.style.width = `${width}px`;
          const colIndex = this.colNames.indexOf(colName);
          if (colIndex >= 0) {
            const nth = colIndex + 2; // +1 за индекс ряда и ещё +1 т.к. nth-child начинается с 1
            this.container.querySelectorAll(`tr td:nth-child(${nth}) input`).forEach(inp => {
              inp.style.width = `${Math.max(20, width - 16)}px`;
            });
          }
        }
      });
    }

    getValue(id) {
      const raw = this.data[id];
      if (!raw) return 0;

      if (raw.startsWith("=")) {
        try {
          const formula = raw.slice(1);

          // SUM
          if (formula.toUpperCase().startsWith("SUM(")) {
            const inside = formula.slice(4, -1);
            const refs = inside.split(",").flatMap(part => {
              if (part.includes(":")) {
                return this.expandRange(part.trim());
              } else {
                return [part.trim()];
              }
            });
            const values = refs.map(ref => parseFloat(this.getValue(ref)) || 0);
            return values.reduce((a, b) => a + b, 0);
          }

          // Простое выражение
          const expr = formula.replace(/[A-Z][0-9]+/g, ref => {
            const val = this.getValue(ref);
            return isNaN(val) ? "0" : val;
          });
          const safeEval = Function('"use strict"; return (' + expr + ');');
          return safeEval();
        } catch {
          return "#ERR";
        }
      }

      return isNaN(raw) ? 0 : parseFloat(raw);
    }

    expandRange(rangeStr) {
      const [start, end] = rangeStr.split(":");
      const colRow = id => {
        const match = id.match(/^([A-Z]+)(\d+)$/);
        return [match[1], parseInt(match[2], 10)];
      };

      const [startCol, startRow] = colRow(start);
      const [endCol, endRow] = colRow(end);

      const cols = this.colNames.filter(c => c >= startCol && c <= endCol);
      const rows = [];
      for (let r = startRow; r <= endRow; r++) rows.push(r);

      const refs = [];
      for (const c of cols) {
        for (const r of rows) {
          refs.push(`${c}${r}`);
        }
      }

      return refs;
    }

    recalculate() {
      const inputs = this.container.querySelectorAll("input");

      inputs.forEach(input => {
        const id = input.dataset.id;
        const raw = this.data[id];

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
      this.colorMap = {}; // сбрасываем
    
      const refs = [...formula.matchAll(/[A-Z][0-9]+/g)].map(m => m[0]);
    
      refs.forEach(ref => {
        const td = this.container.querySelector(`td[data-cell="${ref}"]`);
        if (td) {
          const color = this.getRandomLightColor();
          this.colorMap[ref] = color;
          td.style.backgroundColor = color;
        }
      });
    }


    clearHighlights() {
      this.container.querySelectorAll("td").forEach(td => {
        td.style.backgroundColor = "";
      });
    }
    
    getRandomLightColor() {
      const r = Math.floor(200 + Math.random() * 55);
      const g = Math.floor(200 + Math.random() * 55);
      const b = Math.floor(200 + Math.random() * 55);
      return `rgb(${r}, ${g}, ${b})`;
    }



    togglePointerMode(enable) {
      this.container.querySelectorAll("td").forEach(td => {
        if (enable) {
          td.classList.add("pointer-mode");
        } else {
          td.classList.remove("pointer-mode");
        }
      });
    }

    export() {
      return {
        rows: this.rows,
        cols: this.cols,
        data: { ...this.data },
        colWidths: { ...this.colWidths },
      };
    }

    import(tableObj) {
      if (!tableObj) return;
      const { rows, cols, data, colWidths } = tableObj;
      if (Number.isInteger(rows) && Number.isInteger(cols)) {
        this.rows = rows;
        this.cols = cols;
        this.colNames = Array.from({ length: cols }, (_, i) => String.fromCharCode(65 + i));
        this.data = data || {};
        this.colWidths = colWidths || {};
        this.init();
      } else {
        this.data = data || {};
        this.colWidths = colWidths || {};
        this.applyColumnWidths();
        this.recalculate();
      }
    }
  }
