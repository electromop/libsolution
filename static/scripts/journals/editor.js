

// --- editor.js ---
class EditorManager {
    constructor(editorId) {
        this.editor = document.getElementById(editorId);
    }

    setContent(html) {
        this.editor.innerHTML = html;
    }

    saveCaret() {
        const sel = window.getSelection();
        if (!sel.rangeCount) return null;
        const range = sel.getRangeAt(0);
        const pre = range.cloneRange();
        pre.selectNodeContents(this.editor);
        pre.setEnd(range.startContainer, range.startOffset);
        return { start: pre.toString().length };
    }

    restoreCaret(saved) {
        if (!saved) return;
        let charIndex = 0, node, found = false;
        const rng = document.createRange();
        rng.setStart(this.editor, 0);
        rng.collapse(true);
        const stack = [this.editor];
        while ((node = stack.pop()) && !found) {
            if (node.nodeType === 3) {
                const next = charIndex + node.length;
                if (saved.start >= charIndex && saved.start <= next) {
                    rng.setStart(node, saved.start - charIndex);
                    rng.collapse(true);
                    found = true; break;
                }
                charIndex = next;
            } else {
                for (let i = node.childNodes.length - 1; i >= 0; i--) stack.push(node.childNodes[i]);
            }
        }
        const sel = window.getSelection();
        sel.removeAllRanges(); sel.addRange(rng);
    }

    caretPositionToRange(pos) {
        let charIdx = 0, node, rng = document.createRange();
        const stack = [this.editor];
        while ((node = stack.pop())) {
            if (node.nodeType === 3) {
                const next = charIdx + node.length;
                if (pos >= charIdx && pos <= next) {
                    rng.setStart(node, pos - charIdx); rng.collapse(true); break;
                }
                charIdx = next;
            } else {
                for (let i = node.childNodes.length - 1; i >= 0; i--) stack.push(node.childNodes[i]);
            }
        }
        return rng;
    }

    format(cmd, val = null) {
        document.execCommand(cmd, false, val);
    }

    changeFontSize(size, sendContentUpdate) {
        const selection = window.getSelection();
        if (!selection.rangeCount) return;

        const range = selection.getRangeAt(0);
        if (range.collapsed) return;

        const span = document.createElement("span");
        span.style.fontSize = size + "px";
        span.appendChild(range.extractContents());
        range.insertNode(span);

        // обновить курсор после вставки
        selection.removeAllRanges();
        const newRange = document.createRange();
        newRange.selectNodeContents(span);
        newRange.collapse(false);
        selection.addRange(newRange);

        sendContentUpdate();
    }

    insertTable(rows, cols) {
        if (rows <= 0 || cols <= 0) return;

        let table = document.createElement("table");
        table.style.borderCollapse = "collapse";
        table.style.width = "100%";
        table.style.margin = "10px 0";

        for (let r = 0; r < rows; r++) {
            const tr = document.createElement("tr");
            for (let c = 0; c < cols; c++) {
                const td = document.createElement("td");
                td.style.border = "1px solid #ccc";
                td.style.padding = "5px";
                td.appendChild(document.createTextNode(""));
                tr.appendChild(td);
            }
            table.appendChild(tr);
        }

        const selection = window.getSelection();
        if (!selection.rangeCount) return;

        const range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(table);

        // Ставим курсор после таблицы
        range.setStartAfter(table);
        range.collapse(true);

        selection.removeAllRanges();
        selection.addRange(range);
    }
}