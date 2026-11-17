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

    function renderTwoFactorState(enabled) {
        $("twofa-disabled").classList.toggle("hidden", enabled);
        $("twofa-enrollment").classList.add("hidden");
        $("twofa-enabled").classList.toggle("hidden", !enabled);
        $("twofa-description").textContent = enabled
            ? "Your account is protected with an authenticator app."
            : "Add an authenticator app to protect your account.";
    }

    function renderTwoFactorQr(uri) {
        if (!window.QRCode) throw new Error("The QR code generator could not be loaded.");

        const container = $("twofa-qr");
        container.replaceChildren();
        new window.QRCode(container, {
            text: uri,
            width: 180,
            height: 180,
            colorDark: "#173d2a",
            colorLight: "#ffffff",
            correctLevel: window.QRCode.CorrectLevel.M,
        });
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
        renderTwoFactorState(Boolean(user.is_2fa_enabled));
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

    async function setupTwoFactor() {
        const button = $("twofa-setup");
        button.disabled = true;
        button.textContent = "Creating setup key...";
        clearMessage("twofa-message");

        try {
            const response = await api("/user/2fa/setup", { method: "PATCH" });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            const uri = new URL(result.uri);
            const secret = uri.searchParams.get("secret");
            if (!secret) throw new Error("The server did not return a setup key.");

            renderTwoFactorQr(result.uri);
            $("twofa-secret").value = secret;
            $("twofa-disabled").classList.add("hidden");
            $("twofa-enrollment").classList.remove("hidden");
            $("twofa-code").focus();

        } catch (error) {
            showMessage("twofa-message", error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Set up two-factor authentication";
        }
    }

    async function copyTwoFactorSecret() {
        const secret = $("twofa-secret").value;
        if (!secret) return;

        try {
            await navigator.clipboard.writeText(secret);
            showMessage("twofa-message", "Setup key copied.", "success");
        } catch (error) {
            $("twofa-secret").select();
            showMessage("twofa-message", "Select and copy the setup key manually.");
        }
    }

    async function activateTwoFactor(event) {
        event.preventDefault();
        const form = event.currentTarget;
        if (!form.reportValidity()) return;

        const button = $("twofa-activate");
        button.disabled = true;
        button.textContent = "Verifying...";
        clearMessage("twofa-message");

        try {
            const response = await api("/user/2fa/activate", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: user.email, code: form.code.value.trim() }),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            user = { ...user, is_2fa_enabled: true };
            renderTwoFactorState(true);
            showMessage("twofa-message", result.message || "Two-factor authentication is enabled.", "success");
            toast(result.message || "Two-factor authentication is enabled.");

        } catch (error) {
            showMessage("twofa-message", error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Activate two-factor authentication";
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
            $("twofa-setup").addEventListener("click", setupTwoFactor);
            $("twofa-copy").addEventListener("click", copyTwoFactorSecret);
            $("twofa-form").addEventListener("submit", activateTwoFactor);
            bindPasswordPreviews();

        } catch (error) {
            $("page-message").textContent = error.message;
            $("page-message").classList.add("error");
        }
    }

    init();
});
