
const API_BASE_URL = "http://localhost:8000/api/v1";

const DASHBOARD_URL = "dashboard";
const LOGIN_URL = "login";

// All API requests that use authentication cookies should use this.
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

async function getCurrentUser() {
    const response = await apiRequest("/user/me");

    if (response.status === 401) {
        return null;
    }

    if (!response.ok) {
        throw new Error("Unable to verify your session.");
    }

    return response.json();
}

// Redirect already authenticated users away from login/signup.
async function redirectIfAuthenticated() {
    try {
        const user = await getCurrentUser();

        if (user) {
            window.location.replace(DASHBOARD_URL);
            return true;
        }

        return false;
    } catch (error) {
        console.error("Authentication check failed:", error);
        showMessage("Unable to connect to the server. Please try again.");
        return true;
    }
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

async function verifySessionAndRedirect() {
    const user = await getCurrentUser();

    if (!user) {
        throw new Error("Login succeeded, but the authentication session could not be verified.");
    }

    window.location.replace(DASHBOARD_URL);
}

// Login handler
async function handleLogin(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const button = document.getElementById("submitButton");

    button.disabled = true;
    button.textContent = "Signing in...";

    try {
        const payload = {
            email: form.email.value.trim(),
            password: form.password.value,
        };

        const response = await apiRequest("/user/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(getErrorMessage(data));
        }

        showMessage("Login successful. Redirecting...", "success");

        await verifySessionAndRedirect();

    } catch (error) {
        showMessage(
            error instanceof TypeError
                ? "Unable to connect to the server."
                : error.message
        );
    } finally {
        button.disabled = false;
        button.textContent = "Sign in";
    }
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

// Signup role handling.
function setupRoleSelection() {
    const roleSelect = document.getElementById("requestedRole");
    const supervisorGroup = document.getElementById("supervisorGroup");
    const supervisorSelect = document.getElementById("requestedFrom");

    if (!roleSelect) return;

    function updateRoleFields() {
        const isDeveloper = roleSelect.value === "developer";

        supervisorGroup.classList.toggle("hidden", !isDeveloper);
        supervisorSelect.required = isDeveloper;
    }

    roleSelect.addEventListener("change", updateRoleFields);
    updateRoleFields();
}

// Signup handler
async function handleSignup(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const button = document.getElementById("submitButton");

    button.disabled = true;
    button.textContent = "Creating account...";

    try {
        const role = form.requestedRole.value;

        const payload = {
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
        };

        const response = await apiRequest("/user/signup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(getErrorMessage(data));
        }

        showMessage("Account created successfully. Redirecting...", "success");

        // Your signup endpoint sets the access_token cookie.
        await verifySessionAndRedirect();

    } catch (error) {
        showMessage(
            error instanceof TypeError
                ? "Unable to connect to the server."
                : error.message
        );
    } finally {
        button.disabled = false;
        button.textContent = "Create account";
    }
}

// Initialize authentication pages.
document.addEventListener("DOMContentLoaded", async () => {
    const isAuthPage = document.body.dataset.authPage;

    if (!isAuthPage) return;

    setupPasswordToggle();

    const redirected = await redirectIfAuthenticated();

    if (redirected) return;

    if (isAuthPage === "signup") {
        setupRoleSelection();
        await loadSupervisors();

        document.getElementById("signupForm")
            .addEventListener("submit", handleSignup);
    }

    if (isAuthPage === "login") {
        document.getElementById("loginForm")
            .addEventListener("submit", handleLogin);
    }
});
