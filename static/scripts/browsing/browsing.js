document.addEventListener('DOMContentLoaded', () => {
    class TabManager {
        constructor(tabsContainerId) {
            this.tabsContainer = document.getElementById(tabsContainerId);
            this.currentPageTitle = sessionStorage.getItem('currentPageTitle') || document.title;
            this.currentPageContentId = 'currentPageContent';
            this.currentPageUrl = window.location.href;
            this.init();
        }

        init() {
            this.addCurrentPageToSession();
            this.loadTabsFromSession();
            this.activateCurrentTab();
            this.injectTabStyles();
        }

        injectTabStyles() {
            // Добавляем CSS для уменьшения размера вкладок, названия и крестика
            if (!document.getElementById('tabManagerCustomStyles')) {
                const style = document.createElement('style');
                style.id = 'tabManagerCustomStyles';
                style.innerHTML = `
                    #${this.tabsContainer.id} .nav-item {
                        margin-right: 2px;
                        min-width: 0;
                        max-width: 160px;
                    }
                    #${this.tabsContainer.id} .nav-link {
                        padding: 2px 8px 2px 8px !important;
                        font-size: 1rem !important;
                        min-height: 24px;
                        height: 24px;
                        line-height: 1.1;
                        border-radius: 4px 4px 0 0;
                        max-width: 160px;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }
                    #${this.tabsContainer.id} .nav-link span {
                        font-size: 0.85em;
                        max-width: 110px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                        display: inline-block;
                        vertical-align: middle;
                    }
                    #${this.tabsContainer.id} .bi-x-lg {
                        font-size: 0.9em;
                        margin-left: 4px !important;
                        cursor: pointer;
                        padding: 0;
                        line-height: 1;
                        vertical-align: middle;
                    }
                `;
                document.head.appendChild(style);
            }
        }

        addCurrentPageToSession() {
            let savedTabs = JSON.parse(sessionStorage.getItem('openTabs')) || [];
            if (!savedTabs.some(tab => tab.url === this.currentPageUrl)) {
                savedTabs.push({ title: this.currentPageTitle, contentId: this.currentPageContentId, url: this.currentPageUrl });
                sessionStorage.setItem('openTabs', JSON.stringify(savedTabs));
            }
        }

        loadTabsFromSession() {
            const savedTabs = JSON.parse(sessionStorage.getItem('openTabs')) || [];
            savedTabs.forEach(tabData => {
                const newTab = this.createTabElement(tabData.title, tabData.contentId, tabData.url);
                this.tabsContainer.appendChild(newTab);
            });
        }

        createTabElement(title, contentId, url) {
            const newTab = document.createElement('li');
            newTab.className = 'nav-item';
            newTab.style.minWidth = '0';
            newTab.style.maxWidth = '160px';
            newTab.innerHTML = `
                <button class="nav-link d-flex align-items-center justify-content-between" 
                        style="padding:2px 8px; font-size:0.85rem; min-height:24px; height:24px; max-width:160px;"
                        data-bs-toggle="tab" data-bs-target="#${contentId}" type="button" role="tab" data-url="${url}" onclick="window.location.href='${url}'">
                    <span style="font-size:0.85em; max-width:110px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:inline-block;">${title}</span>
                    <i class="bi bi-x-lg ms-2" aria-label="Close" style="font-size:0.9em; margin-left:4px; cursor:pointer; padding:0; line-height:1;" 
                        onclick="event.stopPropagation(); document.getElementById('${this.tabsContainer.id}').tabManager.closeTab('${url}')"></i>
                </button>
            `;
            return newTab;
        }

        activateCurrentTab() {
            const allTabButtons = this.tabsContainer.querySelectorAll('button.nav-link');
            allTabButtons.forEach(button => {
                if (button.getAttribute('data-url') === this.currentPageUrl) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
            });
        }

        closeTab(url) {
            // Удаление вкладки
            let savedTabs = JSON.parse(sessionStorage.getItem('openTabs')) || [];
            const tabIndex = savedTabs.findIndex(tab => tab.url === url);
            if (tabIndex !== -1) {
                savedTabs.splice(tabIndex, 1);
                sessionStorage.setItem('openTabs', JSON.stringify(savedTabs));
            }
            const tabElement = this.tabsContainer.querySelector(`button[data-url="${url}"]`);
            if (tabElement) {
                const previousTabElement = tabElement.parentElement.previousElementSibling;
                tabElement.parentElement.remove();
                if (previousTabElement) {
                    const previousTabUrl = previousTabElement.querySelector('button').getAttribute('data-url');
                    window.location.href = previousTabUrl;
                }
            }
            this.activateCurrentTab();
        }
    }
    
    if (window.location.href.includes('chemical-details')) {
        document.addEventListener('chemicalDetailsLoaded', () => {
            const tabManager = new TabManager('documentTabs');
            document.getElementById('documentTabs').tabManager = tabManager;
        });
    } else if (window.location.href.includes('document')) {
        document.addEventListener('journalLoaded', () => {
            const tabManager = new TabManager('documentTabs');
            document.getElementById('documentTabs').tabManager = tabManager;
        });
    } else {
        const tabManager = new TabManager('documentTabs');
        document.getElementById('documentTabs').tabManager = tabManager;
    }
});