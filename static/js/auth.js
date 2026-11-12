const API_BASE_URL = "/api/v1";

const DASHBOARD_URL = "/dashboard";
const JOIN_REQUEST_URL = "/create-join-request";

// Where an already signed-in user belongs. No role yet means they still have to ask for one.
function homeFor(role) {
    const value = String(role || "").toLowerCase();

    if (value === "developer") return "/devices";
    if (value === "admin" || value === "supervisor") return DASHBOARD_URL;

    return JOIN_REQUEST_URL;
}

// Error codes the backend can attach to a redirect, e.g. /signin?error=google_failed
const URL_ERRORS = {
    access_rejected: "Your access request has been rejected.",
    google_failed: "Google sign-in failed. Please try again.",
    google_unverified: "Your Google email isn't verified, so it can't be used to sign in.",
};

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

// Already signed in? Skip the form and go straight to where the user belongs.
// A failed check (network error, server down) simply shows the form.
async function redirectIfAuthenticated() {
    try {
        const response = await apiRequest("/user/me");

        if (response.ok) {
            const user = await response.json();
            window.location.replace(homeFor(user.role));
            return true;
        }
    } catch (error) {
        console.error("Authentication check failed:", error);
    }

    return false;
}

function showUrlError() {
    const code = new URLSearchParams(window.location.search).get("error");

    if (code && URL_ERRORS[code]) {
        showMessage(URL_ERRORS[code]);
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

// Sends the request and follows the server's redirect_url.
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

        // Signed in, but access isn't approved yet: the API answers 403 with a
        // message (no "detail") and still sets the cookie.
        const awaitingApproval = response.status === 403 && data?.message && !data?.detail;

        if (!response.ok && !awaitingApproval) {
            throw new Error(getErrorMessage(data));
        }

        redirecting = true;
        showMessage(data.message || successMessage, "success");

        window.location.replace(
            data.redirect_url || (awaitingApproval ? JOIN_REQUEST_URL : DASHBOARD_URL)
        );

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

// Signup only creates the account. The role is requested afterwards on /create-join-request.
function handleSignup(event) {
    event.preventDefault();

    const form = event.currentTarget;

    submitAuthForm({
        endpoint: "/user/signup",
        payload: {
            first_name: form.firstName.value.trim(),
            last_name: form.lastName.value.trim(),
            username: form.username.value.trim(),
            email: form.email.value.trim(),
            password: form.password.value,
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

    showUrlError();

    if (page === "signup") {
        document.getElementById("signupForm")
            .addEventListener("submit", handleSignup);
    }

    if (page === "login") {
        document.getElementById("loginForm")
            .addEventListener("submit", handleLogin);
    }
});