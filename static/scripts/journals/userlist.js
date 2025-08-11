// --- userlist.js ---
class UserListManager {
    constructor(listId) {
        this.list = document.getElementById(listId);
    }

    renderUserList(users) {
        this.list.innerHTML = "";
        users.forEach(u => {
            const li = document.createElement("li");
            li.style.display = 'flex';
            li.style.alignItems = 'center';
            li.style.justifyContent = 'center';

            const avatar = document.createElement('div');
            avatar.textContent = u.avatar || '👤';
            avatar.style.width = '28px';
            avatar.style.height = '28px';
            avatar.style.borderRadius = '50%';
            avatar.style.background = '#f1f3f5';
            avatar.style.display = 'flex';
            avatar.style.alignItems = 'center';
            avatar.style.justifyContent = 'center';
            avatar.style.fontSize = '16px';
            avatar.style.lineHeight = '1';
            avatar.style.border = `2px solid ${u.color || '#ccc'}`;
            avatar.style.margin = '0 4px';
            avatar.title = u.email || u.name || '';

            li.appendChild(avatar);
            this.list.appendChild(li);
        });
    }
}