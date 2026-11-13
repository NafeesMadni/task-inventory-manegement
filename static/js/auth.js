const API_BASE_URL = "/api/v1";

const DASHBOARD_URL = "/dashboard";
const JOIN_REQUEST_URL = "/create-join-request";

// Where an already signed-in user belongs.
function homeFor(role) {
    const value = String(role || "").toLowerCase();

    if (value === "developer") return "/devices";
    if (value === "admin" || value === "supervisor") return DASHBOARD_URL;

    return JOIN_REQUEST_URL;
}

const URL_ERRORS = {
    access_rejected: "Your access request has been rejected.",
    google_failed: "Google sign-in failed. Please try again.",
    google_unverified: "Your Google email isn't verified, so it can't be used to sign in.",
};

// Get Turnstile token independently from the endpoint payload.
function getTurnstileToken(form) {
    const token = new FormData(form).get("cf-turnstile-response");

    if (!token) {
        throw new Error("Please complete the security verification.");
    }

    return token;
}

// All API requests that use authentication cookies go through this.
async function apiRequest(endpoint, options = {}) {
    const {
        turnstileToken,
        headers = {},
        ...fetchOptions
    } = options;

    return fetch(`${API_BASE_URL}${endpoint}`, {
        ...fetchOptions,
        credentials: "include",
        headers: {
            Accept: "application/json",
            ...headers,
            ...(turnstileToken
                ? { "cf-turnstile-response": turnstileToken }
                : {}),
        },
    });
}

function showMessage(message, type = "error") {
    const element = document.getElementById("message");

    if (!element) return;

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

    if (typeof data?.detail?.message === "string") {
        return data.detail.message;
    }

    return data?.message || "Something went wrong. Please try again.";
}

// Already signed in? Redirect to the appropriate page.
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

            if (!input) return;

            const visible = input.type === "password";

            input.type = visible ? "text" : "password";
            button.textContent = visible ? "Hide" : "Show";
        });
    });
}

// Common authentication submission handler.
async function submitAuthForm({
    endpoint,
    payload,
    button,
    form,
    busyLabel,
    idleLabel,
    successMessage
}) {
    button.disabled = true;
    button.textContent = busyLabel;

    let redirecting = false;

    try {
        // Get token separately from JSON payload.
        const turnstileToken = getTurnstileToken(form);

        const response = await apiRequest(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            turnstileToken,
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        // Signed in, but access isn't approved yet.
        const awaitingApproval =
            response.status === 403 &&
            data?.message &&
            !data?.detail;

        if (!response.ok && !awaitingApproval) {
            throw new Error(getErrorMessage(data));
        }

        redirecting = true;

        showMessage(data.message || successMessage, "success");

        window.location.replace(
            data.redirect_url ||
            (awaitingApproval ? JOIN_REQUEST_URL : DASHBOARD_URL)
        );

    } catch (error) {
        showMessage(
            error instanceof TypeError
                ? "Unable to connect to the server."
                : error.message
        );

        // Reset Turnstile after a failed submission because
        // tokens are single-use.
        if (window.turnstile) {
            const widget = document.querySelector(".cf-turnstile");

            if (widget) {
                try {
                    window.turnstile.reset();
                } catch (resetError) {
                    console.error("Turnstile reset failed:", resetError);
                }
            }
        }

    } finally {
        if (!redirecting) {
            button.disabled = false;
            button.textContent = idleLabel;
        }
    }
}

// Login handler.
function handleLogin(event) {
    event.preventDefault();

    const form = event.currentTarget;

    submitAuthForm({
        endpoint: "/user/login",
        form,
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

// Signup handler.
function handleSignup(event) {
    event.preventDefault();

    const form = event.currentTarget;

    submitAuthForm({
        endpoint: "/user/signup",
        form,
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
            ?.addEventListener("submit", handleSignup);
    }

    if (page === "login") {
        document.getElementById("loginForm")
            ?.addEventListener("submit", handleLogin);
    }
});
