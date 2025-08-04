// --- main.js ---
document.addEventListener("DOMContentLoaded", () => {
    const editorManager = new EditorManager("editor");
    const userListManager = new UserListManager("user-list");
    const cursorManager = new CursorManager(editorManager);

    // Получаем journal_id из URL
    let journalId = null;
    const match = window.location.pathname.match(/\/journal\/(\d+)/);
    if (match) {
        journalId = match[1];
    }

    const wsManager = new WebSocketManager(
        `wss://${location.host}/ws/journal/${journalId}`,
        editorManager,
        userListManager,
        cursorManager
    );

    // Toolbar
    window.format = (cmd, val = null) => editorManager.format(cmd, val);

    window.changeFontSize = (size) => {
        editorManager.changeFontSize(size, () => wsManager.sendContentUpdateDebounced());
    };
});