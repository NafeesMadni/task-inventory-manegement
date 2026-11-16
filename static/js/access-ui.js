/* =========================================================
   Device Portal – return a device / revoke access
   One confirmation dialog (#rs-dialog in devices.html) shared by:
     - My Devices:  a holder returns their own device         (mode "return")
     - History:     an admin takes a device back from a user  (mode "revoke")
   The server decides which one it was: if the person acting is the holder it records a return,
   otherwise a revocation. Load after shell.js and device-ui.js.
   ========================================================= */

const AccessUI = (() => {
    const { $, api, escapeHTML, toast, errorMessage } = Portal;

    // Route of the reset-access endpoint (relative to /api/v1).
    const RESET_PATH = "/device/reset-access";

    const COPY = {
        return: {
            eyebrow: "Return device",
            title: "Return this device?",
            noteLabel: "Note (optional)",
            placeholder: "e.g. No longer needed for my project",
            submit: "Return device",
            danger: false,
        },
        revoke: {
            eyebrow: "Revoke access",
            title: "Revoke access?",
            noteLabel: "Reason (optional)",
            placeholder: "e.g. Left the team, device needed elsewhere",
            submit: "Revoke access",
            danger: true,
        },
    };

    let bound = false;
    let context = null; // what the open dialog is about

    function bind() {
        if (bound) return;
        bound = true;

        $("rs-close").addEventListener("click", close);
        $("rs-cancel").addEventListener("click", close);
        $("rs-form").addEventListener("submit", submit);

        $("rs-dialog").addEventListener("click", event => {
            if (event.target === event.currentTarget) close(); // backdrop click
        });
    }

    function close() {
        $("rs-dialog").close();
    }

    function showError(text) {
        const box = $("rs-message");
        box.textContent = text;
        box.className = "message show error";
    }

    // mode: "return" | "revoke"
    // onDone: called after the server accepted the change (reload your list there).
    function open({ mode, deviceId, deviceName, holderId, holderName, onDone }) {
        bind();

        const copy = COPY[mode];
        context = { deviceId, holderId, onDone };

        $("rs-form").reset();
        $("rs-message").className = "message";

        $("rs-eyebrow").textContent = copy.eyebrow;
        $("rs-title").textContent = copy.title;
        $("rs-note-label").textContent = copy.noteLabel;
        $("rs-note").placeholder = copy.placeholder;

        $("rs-text").innerHTML = mode === "return"
            ? `<strong>${escapeHTML(deviceName)}</strong> will go back to the inventory and be available again.`
            : `<strong>${escapeHTML(deviceName)}</strong> will be taken back from <strong>${escapeHTML(holderName)}</strong>. ` +
              `They lose access to it, and it becomes available again.`;

        const submitButton = $("rs-submit");
        submitButton.disabled = false;
        submitButton.textContent = copy.submit;
        submitButton.className = `btn btn-lg ${copy.danger ? "btn-danger" : "btn-primary"}`;

        $("rs-dialog").showModal();
    }

    async function submit(event) {
        event.preventDefault();

        const submitButton = $("rs-submit");
        const label = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = "Working...";
        $("rs-message").className = "message";

        try {
            const note = $("rs-note").value.trim();

            const response = await api(RESET_PATH, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    device_id: context.deviceId,
                    current_holder_id: context.holderId,
                    return_note: note || null,
                }),
            });
            if (!response) return;

            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorMessage(result, response.status));

            DeviceUI.invalidateMine(); // the user's own device list has changed
            close();
            toast(result.message || "Done.");
            await context.onDone?.();

        } catch (error) {
            showError(error instanceof TypeError ? "Unable to connect to the server." : error.message);
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = label;
        }
    }

    return { open };
})();