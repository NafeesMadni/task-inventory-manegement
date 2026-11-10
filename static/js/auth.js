const API_BASE_URL = "/api/v1";
const DASHBOARD_URL = "/dashboard";

// All API requests that use authentication cookies go through this.
async function apiRequest(endpoint, options = {}) {
    return fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        credentials: "include",
        headers: {
            Accept: "application/json",
            ...options.headers,
        },
    });
}

function showMessage(message, type = "error") {
    const element = document.getElementById("message");

    element.textContent = message;
    element.className = `message show ${type}`;
}

function getErrorMessage(data) {
    if (typeof data?.detail === "string") {
        return data.detail;
    }

    if (Array.isArray(data?.detail)) {
        return data.detail.map(error => error.msg).join(", ");
    }

    return data?.message || "Something went wrong. Please try again.";
}

// Already signed in? Skip the form and go straight to the dashboard.
// A failed check (network error, server down) simply shows the form.
async function redirectIfAuthenticated() {
    try {
        const response = await apiRequest("/user/me");

        if (response.ok) {
            window.location.replace(DASHBOARD_URL);
            return true;
        }
    } catch (error) {
        console.error("Authentication check failed:", error);
    }

    return false;
}

function setupPasswordToggle() {
    document.querySelectorAll("[data-password-toggle]").forEach(button => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            const visible = input.type === "password";

            input.type = visible ? "text" : "password";
            button.textContent = visible ? "Hide" : "Show";
        });
    });
}

// Sends the request and, on success, goes straight to the dashboard.
// The cookie is already set by the response, so no extra /me call is needed.
async function submitAuthForm({ endpoint, payload, button, busyLabel, idleLabel, successMessage }) {
    button.disabled = true;
    button.textContent = busyLabel;

    let redirecting = false;

    try {
        const response = await apiRequest(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(getErrorMessage(data));
        }

        redirecting = true;
        showMessage(successMessage, "success");
        window.location.replace(DASHBOARD_URL);

    } catch (error) {
        showMessage(
            error instanceof TypeError
                ? "Unable to connect to the server."
                : error.message
        );
    } finally {
        if (!redirecting) {
            button.disabled = false;
            button.textContent = idleLabel;
        }
    }
}

function handleLogin(event) {
    event.preventDefault();

    const form = event.currentTarget;

    submitAuthForm({
        endpoint: "/user/login",
        payload: {
            email: form.email.value.trim(),
            password: form.password.value,
        },
        button: document.getElementById("submitButton"),
        busyLabel: "Signing in...",
        idleLabel: "Sign in",
        successMessage: "Signed in. Redirecting...",
    });
}

// Load supervisors for developer signup.
async function loadSupervisors() {
    const select = document.getElementById("requestedFrom");

    if (!select) return;

    try {
        const response = await apiRequest("/user/supervisors");

        if (!response.ok) {
            throw new Error("Unable to load supervisors.");
        }

        const data = await response.json();

        const supervisors = Array.isArray(data)
            ? data
            : data.supervisors || data.items || [];

        select.innerHTML = '<option value="">Select a supervisor</option>';

        supervisors.forEach(supervisor => {
            const option = document.createElement("option");

            option.value = supervisor.id;
            option.textContent =
                `${supervisor.first_name} ${supervisor.last_name} (@${supervisor.username})`;

            select.appendChild(option);
        });

    } catch (error) {
        console.error(error);
        showMessage("Unable to load supervisors. Please try again.");
    }
}

// Signup: show supervisor picker for developers, and reflect the chosen role
// in the page title badge.
function setupRoleSelection() {
    const roleSelect = document.getElementById("requestedRole");
    const supervisorGroup = document.getElementById("supervisorGroup");
    const supervisorSelect = document.getElementById("requestedFrom");
    const badge = document.getElementById("roleBadge");

    if (!roleSelect) return;

    function updateRoleFields() {
        const role = roleSelect.value;
        const isDeveloper = role === "developer";

        supervisorGroup.classList.toggle("hidden", !isDeveloper);
        supervisorSelect.required = isDeveloper;

        if (badge) {
            badge.textContent = role;
            badge.className = `role-badge ${role}`;
        }
    }

    roleSelect.addEventListener("change", updateRoleFields);
    updateRoleFields();
}

function handleSignup(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const role = form.requestedRole.value;

    submitAuthForm({
        endpoint: "/user/signup",
        payload: {
            first_name: form.firstName.value.trim(),
            last_name: form.lastName.value.trim(),
            username: form.username.value.trim(),
            email: form.email.value.trim(),
            password: form.password.value,
            requested_role: role,
            requested_from: role === "developer"
                ? Number(form.requestedFrom.value)
                : null,
            request_note: form.requestNote.value.trim() || null,
        },
        button: document.getElementById("submitButton"),
        busyLabel: "Creating account...",
        idleLabel: "Create account",
        successMessage: "Account created. Redirecting...",
    });
}

// Initialize authentication pages.
document.addEventListener("DOMContentLoaded", async () => {
    const page = document.body.dataset.authPage;

    if (!page) return;

    setupPasswordToggle();

    if (await redirectIfAuthenticated()) return;

    if (page === "signup") {
        setupRoleSelection();
        await loadSupervisors();

        document.getElementById("signupForm")
            .addEventListener("submit", handleSignup);
    }

    if (page === "login") {
        document.getElementById("loginForm")
            .addEventListener("submit", handleLogin);
    }
});