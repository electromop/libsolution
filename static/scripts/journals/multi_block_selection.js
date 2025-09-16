// --- multi_block_selection.js ---
// Класс для управления выделением текста из нескольких блоков
class MultiBlockSelection {
    constructor(blockEditorManager) {
        this.blockEditorManager = blockEditorManager;
        this.container = blockEditorManager.container;
        this.isSelecting = false;
        this.selectionRange = null;
        this.affectedBlocks = new Set();
        
        this.init();
    }

    init() {
        // Добавляем обработчики событий для выделения
        this.container.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.container.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.container.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.container.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Обработка выделения с клавиатуры
        this.container.addEventListener('keyup', (e) => this.handleKeyUp(e));
        
        // Отслеживаем изменения выделения
        document.addEventListener('selectionchange', () => this.handleSelectionChange());
        
        // Обработчик для выделения между блоками
        this.container.addEventListener('selectstart', (e) => this.handleSelectStart(e));
    }

    handleSelectStart(e) {
        // Если клик по drag handle, не начинаем выделение
        if (e.target.closest('.drag-handle')) return;

        this.isSelecting = true;
        // Позволяем браузеру обработать выделение текста
    }

    handleMouseDown(e) {
        // Если клик по drag handle, не начинаем выделение
        if (e.target.closest('.drag-handle')) return;

        this.isSelecting = true;
        // Позволяем браузеру обработать выделение текста
    }

    handleMouseMove(e) {
        if (!this.isSelecting) return;
        // Позволяем браузеру обработать выделение текста
    }

    handleMouseUp(e) {
        if (!this.isSelecting) return;
        
        this.isSelecting = false;
        this.updateAffectedBlocks();
    }

    handleSelectionChange() {
        // Обновляем информацию о выделении при изменении
        this.updateAffectedBlocks();
    }

    handleKeyDown(e) {
        // Обработка Delete и Backspace для удаления выделенного текста
        if ((e.key === 'Delete' || e.key === 'Backspace') && this.hasSelection()) {
            e.preventDefault();
            this.deleteSelection();
            return;
        }

        // Обработка Escape для снятия выделения
        if (e.key === 'Escape') {
            this.clearSelection();
            return;
        }

        // Обработка Ctrl+A для выделения всего текста
        if (e.key === 'a' && e.ctrlKey) {
            e.preventDefault();
            this.selectAllText();
            return;
        }

        // Обработка Ctrl+C для копирования выделенного текста
        if (e.key === 'c' && e.ctrlKey && this.hasSelection()) {
            // Позволяем браузеру обработать копирование
            return;
        }
    }

    handleKeyUp(e) {
        // Обновляем информацию о выделении при изменении с клавиатуры
        this.updateAffectedBlocks();
    }

    updateAffectedBlocks() {
        this.affectedBlocks.clear();
        this.clearVisualSelection();
        
        const selection = window.getSelection();
        if (!selection.rangeCount) return;

        const range = selection.getRangeAt(0);
        if (range.collapsed) return;

        // Находим все блоки, которые содержат выделенный текст
        const startBlock = range.startContainer.closest('.editor-block');
        const endBlock = range.endContainer.closest('.editor-block');
        
        if (!startBlock || !endBlock) return;

        // Если выделение в одном блоке, просто подсвечиваем его
        if (startBlock === endBlock) {
            this.affectedBlocks.add(startBlock);
            this.highlightBlock(startBlock);
            return;
        }

        // Добавляем все блоки между началом и концом выделения
        const allBlocks = Array.from(this.container.querySelectorAll('.editor-block'));
        const startIndex = allBlocks.indexOf(startBlock);
        const endIndex = allBlocks.indexOf(endBlock);
        
        const start = Math.min(startIndex, endIndex);
        const end = Math.max(startIndex, endIndex);
        
        for (let i = start; i <= end; i++) {
            if (allBlocks[i]) {
                this.affectedBlocks.add(allBlocks[i]);
                this.highlightBlock(allBlocks[i]);
            }
        }
    }

    selectAllText() {
        // Выделяем весь текст во всех блоках
        const range = document.createRange();
        const allBlocks = Array.from(this.container.querySelectorAll('.editor-block .block-content'));
        
        if (allBlocks.length === 0) return;
        
        // Начинаем с первого блока
        const firstBlock = allBlocks[0];
        const lastBlock = allBlocks[allBlocks.length - 1];
        
        // Выделяем от начала первого блока до конца последнего
        range.setStart(firstBlock, 0);
        range.setEnd(lastBlock, lastBlock.childNodes.length);
        
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        
        this.updateAffectedBlocks();
    }

    highlightBlock(block) {
        block.classList.add('has-text-selection');
    }

    clearVisualSelection() {
        this.container.querySelectorAll('.has-text-selection').forEach(block => {
            block.classList.remove('has-text-selection');
        });
    }

    hasSelection() {
        const selection = window.getSelection();
        return selection.rangeCount > 0 && !selection.getRangeAt(0).collapsed;
    }

    clearSelection() {
        const selection = window.getSelection();
        selection.removeAllRanges();
        this.clearVisualSelection();
        this.affectedBlocks.clear();
    }

    deleteSelection() {
        if (!this.hasSelection()) return;

        const selection = window.getSelection();
        const range = selection.getRangeAt(0);
        
        // Удаляем выделенный текст
        range.deleteContents();
        
        // Обновляем блоки, которые были изменены
        this.updateAffectedBlocks();
        
        // Очищаем выделение
        this.clearSelection();
    }

    getSelectedText() {
        const selection = window.getSelection();
        if (!selection.rangeCount) return '';
        
        return selection.toString();
    }

    getSelectedHTML() {
        const selection = window.getSelection();
        if (!selection.rangeCount) return '';
        
        const range = selection.getRangeAt(0);
        const contents = range.cloneContents();
        
        // Создаем временный контейнер для получения HTML
        const temp = document.createElement('div');
        temp.appendChild(contents);
        
        return temp.innerHTML;
    }
}
