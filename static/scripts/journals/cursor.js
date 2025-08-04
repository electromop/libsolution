// --- cursor.js ---
class CursorManager {
    constructor(editorManager) {
        this.editorManager = editorManager;
        this.cursors = {};
    }

    showCursor(uid, pos) {
        this.removeCursor(uid);
        const range = this.editorManager.caretPositionToRange(pos);
        const rect = range.getBoundingClientRect();
        const editorRect = this.editorManager.editor.getBoundingClientRect();
        const curEl = document.createElement("div");
        curEl.className = "cursor";
        curEl.style.background = this.managerColor(uid);
        curEl.style.left = (rect.left - editorRect.left) + "px";
        curEl.style.top = (rect.top - editorRect.top) + "px";
        this.editorManager.editor.append(curEl);
        this.cursors[uid] = curEl;
    }

    removeCursor(uid) {
        const el = this.cursors[uid];
        if (el) el.remove();
    }

    managerColor(uid) {
        // простая ассоциация: пользуем UUID hash
        return "hsl(" + (uid.split("-")[0].match(/\d+/) || [0])[0] % 360 + ",70%,50%)";
    }
}