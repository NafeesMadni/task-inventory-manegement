/* Device Portal – complete an authenticated two-factor sign-in. */

const TWO_FA_API = "/api/v1";

const twoFaHomeFor = role => {
    const value = String(role || "").toLowerCase();
    if (value === "developer") return "/devices";
    if (value === "admin" || value === "supervisor") return "/dashboard";
    return "/create-join-request";
};

const twoFaError = data => {
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
    return "Unable to verify the code. Please try again.";
};

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("twofa-verify-form");
    const message = document.getElementById("message");
    const button = document.getElementById("submit-button");
    const savedEmail = sessionStorage.getItem("twofa-email");

    if (savedEmail) form.email.value = savedEmail;

    const showMessage = (text, type = "error") => {
        message.textContent = text;
        message.className = `message show ${type}`;
    };

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;

        button.disabled = true;
        button.textContent = "Verifying...";
        message.className = "message";

        try {
            const response = await fetch(`${TWO_FA_API}/user/2fa/verify`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify({
                    email: form.email.value.trim(),
                    code: form.code.value.trim(),
                }),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(twoFaError(result));

            const me = await fetch(`${TWO_FA_API}/user/me`, { credentials: "include" });
            if (!me.ok) throw new Error("Sign-in could not be completed. Please sign in again.");

            const user = await me.json();
            sessionStorage.removeItem("twofa-email");
            showMessage(result.message || "Verified. Redirecting...", "success");
            window.location.replace(twoFaHomeFor(user.role));

        } catch (error) {
            showMessage(error instanceof TypeError ? "Unable to connect to the server." : error.message);
            button.disabled = false;
            button.textContent = "Verify and sign in";
        }
    });
});
