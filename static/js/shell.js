/* =========================================================
   Device Portal – shared shell
   Renders the site header, builds the nav from the user's role,
   handles logout and exposes the helpers every page needs.

   Usage in a page:
     <header class="site-header" id="site-header"></header>
     <script src="/static/js/shell.js"></script>
     <script>
       const { $, api, escapeHTML, toast } = Portal;
       const session = await Portal.start({ title: "Devices" });
       if (!session) return;            // redirected to /signin
       const { user, role } = session;
     </script>
   ========================================================= */

const Portal = (() => {
    const API = "/api/v1";
    const SITE = "Device Portal";

    // Single source of truth for navigation: add a page here and every header gets it.
    const NAV = [
        { href: "/dashboard", label: "Dashboard", roles: ["admin", "supervisor"] },
        { href: "/devices", label: "Devices", roles: ["admin", "supervisor", "developer"] },
    ];

    let role = "pending";
    let currentUser = null;

    /* ---------- Helpers ---------- */

    const $ = id => document.getElementById(id);

    const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[char]);

    const pretty = value => String(value ?? "").replace(/_/g, " ").toLowerCase();

    let toastTimer;
    function toast(message, type = "success") {
        let el = $("toast");

        if (!el) {
            el = document.createElement("div");
            el.id = "toast";
            el.setAttribute("role", "status");
            document.body.appendChild(el);
        }

        el.textContent = message;
        el.className = `toast show ${type === "error" ? "error" : ""}`;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
    }

    // Returns the response, or null after sending an unauthenticated user to sign in.
    async function api(path, options = {}) {
        const response = await fetch(`${API}${path}`, { credentials: "include", ...options });

        if (response.status === 401) {
            window.location.replace("/signin");
            return null;
        }

        return response;
    }

    function errorMessage(data, status) {
        if (typeof data?.detail === "string") return data.detail;

        if (Array.isArray(data?.detail)) {
            return data.detail
                .map(e => `${(e.loc || []).slice(1).join(" ")}: ${e.msg}`.replace(/^: /, ""))
                .join(" · ");
        }

        if (data?.message) return data.message;

        return status >= 500
            ? "The server couldn't process this request. Please try again."
            : "Something went wrong. Please try again.";
    }

    /* ---------- Header ---------- */

    function renderShell() {
        const header = $("site-header");
        if (!header) return;

        header.innerHTML = `
            <div class="header-inner">
                <a href="/" class="brand">
                    <span class="brand-logo">D</span>
                    <span>${SITE}</span>
                </a>

                <nav class="site-nav" id="site-nav"></nav>

                <div class="header-right">
                    <div class="user-chip">
                        <span class="avatar sm" id="user-avatar">·</span>
                        <span class="user-name" id="user-info">Loading...</span>
                    </div>
                    <button class="btn" id="profile-btn">Profile</button>
                    <a href="/create-join-request" class="btn btn-primary hidden" id="request-access-btn">Request access</a>
                    <button class="btn" id="logout-btn">Logout</button>
                </div>
            </div>

            <dialog class="modal" id="profile-dialog">
                <form id="profile-form" novalidate>
                    <div class="modal-head">
                        <div>
                            <p class="eyebrow">Account</p>
                            <h2>Edit profile</h2>
                        </div>
                        <button type="button" class="icon-btn" id="profile-close" aria-label="Close">&times;</button>
                    </div>

                    <p class="subtitle">Update the information shown across the portal.</p>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="profile-first-name">First name</label>
                            <input type="text" id="profile-first-name" name="first_name" maxlength="100" required>
                        </div>
                        <div class="form-group">
                            <label for="profile-last-name">Last name</label>
                            <input type="text" id="profile-last-name" name="last_name" maxlength="100" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="profile-username">Username</label>
                        <input type="text" id="profile-username" name="username" minlength="3" maxlength="100" required>
                    </div>

                    <div id="profile-message" class="message" role="alert"></div>

                    <div class="modal-actions">
                        <button type="button" class="btn btn-lg" id="profile-cancel">Cancel</button>
                        <button type="submit" class="btn btn-primary btn-lg" id="profile-submit">Save changes</button>
                    </div>
                </form>
            </dialog>`;

        $("logout-btn").addEventListener("click", logout);
        $("profile-btn").addEventListener("click", openProfile);
        $("profile-close").addEventListener("click", closeProfile);
        $("profile-cancel").addEventListener("click", closeProfile);
        $("profile-form").addEventListener("submit", submitProfile);
        $("profile-dialog").addEventListener("click", event => {
            if (event.target === event.currentTarget) closeProfile();
        });
    }

    function fillUser(user) {
        currentUser = user;
        const first = user.first_name || "";
        const last = user.last_name || "";

        $("user-info").innerHTML =
            `${escapeHTML(`${first} ${last}`.trim())} ` +
            `<span class="role-badge ${escapeHTML(role)}">${escapeHTML(role)}</span>`;
        $("user-avatar").textContent = `${first[0] || ""}${last[0] || ""}`.toUpperCase() || "·";

        const here = location.pathname.replace(/\/+$/, "") || "/";

        // Signed in but no role yet: always offer the way to ask for access.
        $("request-access-btn").classList.toggle(
            "hidden", role !== "pending" || here === "/create-join-request");

        $("site-nav").innerHTML = NAV
            .filter(link => link.roles.includes(role))
            .map(link =>
                `<a href="${link.href}" class="nav-link${link.href === here ? " active" : ""}">${link.label}</a>`)
            .join("");

        // Highlight the viewer's role next to any page title that asks for it.
        document.querySelectorAll("[data-role-badge]").forEach(badge => {
            badge.textContent = role;
            badge.classList.add(role);
        });
    }

    function openProfile() {
        if (!currentUser) return;

        const form = $("profile-form");
        form.first_name.value = currentUser.first_name || "";
        form.last_name.value = currentUser.last_name || "";
        form.username.value = currentUser.username || "";
        $("profile-message").className = "message";
        $("profile-submit").disabled = false;
        $("profile-submit").textContent = "Save changes";
        $("profile-dialog").showModal();
        $("profile-first-name").focus();
    }

    function closeProfile() {
        $("profile-dialog").close();
    }

    function showProfileError(message) {
        const box = $("profile-message");
        box.textContent = message;
        box.className = "message show error";
    }

    async function submitProfile(event) {
        event.preventDefault();
        if (!currentUser) return;

        const form = event.currentTarget;
        if (!form.reportValidity()) return;

        const values = {
            first_name: form.first_name.value.trim(),
            last_name: form.last_name.value.trim(),
            username: form.username.value.trim(),
        };
        const payload = Object.fromEntries(Object.entries(values).filter(
            ([field, value]) => value !== String(currentUser[field] || "")
        ));

        if (!Object.keys(payload).length) {
            closeProfile();
            return;
        }

        const button = $("profile-submit");
        button.disabled = true;
        button.textContent = "Saving...";
        $("profile-message").className = "message";

        try {
            const response = await api("/user", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            fillUser({ ...currentUser, ...payload });
            closeProfile();
            toast(result.message || "Profile updated.");

        } catch (error) {
            showProfileError(error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Save changes";
        }
    }

    async function logout() {
        try {
            const response = await api("/user/logout", { method: "POST" });
            if (!response) return;

            if (!response.ok) {
                const result = await response.json().catch(() => ({}));
                throw new Error(result.message || "Logout failed.");
            }

            window.location.replace("/signin");

        } catch (error) {
            toast(error.message || "Unable to logout.", "error");
        }
    }

    // Message shown when a signed-in user has nothing to see on a page.
    // Users without a role also get a button to the join-request page.
    function noAccessHTML(userRole, what) {
        const badge = `<span class="role-badge ${escapeHTML(userRole)}">${escapeHTML(userRole)}</span>`;

        return `<div class="no-access">
                    <p>Your account (${badge}) doesn't have access to ${what} yet.</p>
                    ${userRole === "pending"
                        ? `<a href="/create-join-request" class="btn btn-primary btn-lg">Request access</a>`
                        : ""}
                </div>`;
    }

    function setTitle(label) {
        document.title = `${label} · ${role} | ${SITE}`;
    }

    /* ---------- Session ---------- */

    // Verifies the session once, fills the header and returns { user, role }.
    // Returns null when the visitor was sent to /signin.
    async function start({ title } = {}) {
        const response = await api("/user/me");

        if (!response) return null;
        if (!response.ok) throw new Error("Unable to verify your account.");

        const user = await response.json();
        role = String(user.role || "pending").toLowerCase();

        fillUser(user);
        if (title) setTitle(title);

        return { user, role };
    }

    // Draw the header right away so it never pops in late.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", renderShell);
    } else {
        renderShell();
    }

    return { $, api, escapeHTML, pretty, toast, errorMessage, noAccessHTML, setTitle, start };
})();
