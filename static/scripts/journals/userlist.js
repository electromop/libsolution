// --- userlist.js ---
class UserListManager {
    constructor(listId) {
        this.list = document.getElementById(listId);
    }

    renderUserList(users) {
        this.list.innerHTML = "";
        users.forEach(u => {
            const li = document.createElement("li");
            li.innerHTML = `<span style="color:${u.color}; font-weight:bold;">●</span> ${u.name}`;
            this.list.appendChild(li);
        });
    }
}