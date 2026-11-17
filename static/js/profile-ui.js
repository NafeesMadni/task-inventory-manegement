/* Device Portal – profile and password settings page */

document.addEventListener("DOMContentLoaded", () => {
    const { $, api, errorMessage, toast } = Portal;
    let user = null;

    function showMessage(id, message, type = "error") {
        const box = $(id);
        box.textContent = message;
        box.className = `message show ${type}`;
    }

    function clearMessage(id) {
        $(id).className = "message";
    }

    function bindPasswordPreviews() {
        document.querySelectorAll("[data-password-toggle]").forEach(button => {
            button.addEventListener("click", () => {
                const input = $(button.dataset.passwordToggle);
                const visible = input.type === "password";

                input.type = visible ? "text" : "password";
                button.textContent = visible ? "Hide" : "Show";
            });
        });
    }

    function fillProfile(nextUser) {
        user = nextUser;
        $("profile-first-name").value = user.first_name || "";
        $("profile-last-name").value = user.last_name || "";
        $("profile-username").value = user.username || "";
        $("profile-email").value = user.email || "";

        const role = String(user.role || "pending").toLowerCase();
        const badge = $("profile-role");
        badge.textContent = role;
        badge.className = `role-badge ${role}`;
    }

    async function refreshUser() {
        const response = await api("/user/me");
        if (!response || !response.ok) throw new Error("Unable to load your profile.");

        const nextUser = await response.json();
        fillProfile(nextUser);
        return nextUser;
    }

    async function saveProfile(event) {
        event.preventDefault();
        const form = event.currentTarget;
        if (!form.reportValidity() || !user) return;

        const values = {
            first_name: form.first_name.value.trim(),
            last_name: form.last_name.value.trim(),
            username: form.username.value.trim(),
        };
        const payload = Object.fromEntries(Object.entries(values).filter(
            ([field, value]) => value !== String(user[field] || "")
        ));

        if (!Object.keys(payload).length) {
            showMessage("profile-message", "There are no changes to save.", "success");
            return;
        }

        const button = $("profile-submit");
        button.disabled = true;
        button.textContent = "Saving...";
        clearMessage("profile-message");

        try {
            const response = await api("/user", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            await refreshUser();
            showMessage("profile-message", result.message || "Profile updated.", "success");
            toast(result.message || "Profile updated.");

        } catch (error) {
            showMessage("profile-message", error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Save profile";
        }
    }

    async function savePassword(event) {
        event.preventDefault();
        const form = event.currentTarget;
        if (!form.reportValidity()) return;

        const oldPassword = form.old_password.value;
        const newPassword = form.new_password.value;
        if (newPassword !== $("confirm-password").value) {
            showMessage("password-message", "The new passwords do not match.");
            return;
        }

        const button = $("password-submit");
        button.disabled = true;
        button.textContent = "Updating...";
        clearMessage("password-message");

        try {
            const response = await api("/user/password", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            form.reset();
            showMessage("password-message", result.message || "Password updated.", "success");
            toast(result.message || "Password updated.");

        } catch (error) {
            showMessage("password-message", error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Update password";
        }
    }

    async function init() {
        try {
            const session = await Portal.start({ title: "Profile" });
            if (!session) return;

            fillProfile(session.user);
            $("page-message").classList.add("hidden");
            $("profile-page").classList.remove("hidden");
            $("profile-form").addEventListener("submit", saveProfile);
            $("password-form").addEventListener("submit", savePassword);
            bindPasswordPreviews();

        } catch (error) {
            $("page-message").textContent = error.message;
            $("page-message").classList.add("error");
        }
    }

    init();
});
