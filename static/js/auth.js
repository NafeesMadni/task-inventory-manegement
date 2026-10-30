const API_URL = "/api/v1/auth";

function showForm(type) {
    document.getElementById("login-form").hidden = type !== "login";
    document.getElementById("signup-form").hidden = type !== "signup";
}

function showMessage(message) {
    document.getElementById("message").textContent = message;
}


// Signup API
document.getElementById("signup-form").addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const payload = {
            username: document.getElementById("signup-username").value,
            email: document.getElementById("signup-email").value,
            password: document.getElementById("signup-password").value,
        };

        const response = await fetch(`${API_URL}/signup`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        showMessage(
            response.ok ? "Account created successfully!" :
            data.detail || "Signup failed"
        );
    }
);


// Login API
document.getElementById("login-form").addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const payload = {
            email: document.getElementById("login-email").value,
            password: document.getElementById("login-password").value,
        };

        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        showMessage(
            response.ok ? "Login successful!" :
            data.detail || "Invalid credentials"
        );
    }
);