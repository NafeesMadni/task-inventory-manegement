/* =========================================================
   Device Portal – voice input for device forms
   Record on the spot or upload an audio file; the API transcribes it and returns the device fields,
   which are put into the form for the admin to review and edit before saving.

   Usage:
     const voice = VoiceUI.mount(document.getElementById("slot"), { form: formElement, actionLabel: "add the device" });
     voice.reset();   // call when the dialog opens or closes
   The form's inputs must be named like the API fields (name, brand, serial_no, processor,
   ram_gb, ssd_gb, hdd_gb, purchase_date, purchase_price).
   Styles: static/css/voice.css. Load after shell.js.
   ========================================================= */

const VoiceUI = (() => {
    const { api, escapeHTML, errorMessage } = Portal;

    // Endpoints (relative to /api/v1).
    const INIT_PATH = "/transcribe/init-process";
    const statusPath = id => `/transcribe/task-status/${encodeURIComponent(id)}`;

    const MAX_RECORD_SECONDS = 120; // a recording stops by itself after this long
    const MAX_UPLOAD_MB = 10;       // larger files are refused before uploading
    const POLL_MS = 1500;           // how often the result is checked
    const MAX_WAIT_MS = 120000;     // give up waiting after this long

    const LABELS = {
        name: "Name",
        brand: "Brand",
        serial_no: "Serial number",
        processor: "Processor",
        ram_gb: "RAM",
        ssd_gb: "SSD",
        hdd_gb: "HDD",
        purchase_date: "Purchase date",
        purchase_price: "Purchase price",
    };
    const FIELD_KEYS = Object.keys(LABELS);

    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const clock = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

    // Recording needs a secure page (HTTPS or localhost) and MediaRecorder support.
    const canRecord = () =>
        Boolean(typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined");

    function pickMime() {
        const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
        return types.find(type => MediaRecorder.isTypeSupported(type)) || "";
    }

    function extensionFor(mime) {
        if (mime.includes("mp4")) return "m4a";
        if (mime.includes("ogg")) return "ogg";
        if (mime.includes("wav")) return "wav";
        return "webm";
    }

    const looksLikeAudio = file =>
        String(file.type).startsWith("audio/") || /\.(mp3|m4a|wav|webm|ogg|mp4|mpeg|mpga|flac)$/i.test(file.name || "");

    function mount(slot, { form, actionLabel = "save" }) {
        slot.innerHTML = `
            <div class="voice">
                <div class="voice-title">Fill from voice</div>
                <div class="voice-bar">
                    <button type="button" class="btn voice-rec"><span class="voice-dot"></span><span class="voice-rec-label">Record</span></button>
                    <button type="button" class="btn voice-upload">Upload audio</button>
                    <input type="file" class="voice-file" accept="audio/*,video/webm,.m4a,.mp3,.wav,.webm,.ogg" hidden>
                </div>
                <p class="voice-hint">Say the name, brand, serial number, processor, RAM, storage, purchase date and price.
                    You can review and edit everything before saving.</p>
                <div class="voice-status hidden" role="status"></div>
                <div class="voice-review hidden"></div>
            </div>`;

        const recBtn = slot.querySelector(".voice-rec");
        const recLabel = slot.querySelector(".voice-rec-label");
        const uploadBtn = slot.querySelector(".voice-upload");
        const fileInput = slot.querySelector(".voice-file");
        const hint = slot.querySelector(".voice-hint");
        const statusBox = slot.querySelector(".voice-status");
        const reviewBox = slot.querySelector(".voice-review");

        let runId = 0;          // bumped to cancel anything still in flight
        let recorder = null;
        let stream = null;
        let chunks = [];
        let timerId = null;
        let startedAt = 0;
        let discard = false;    // true when a recording is stopped without being used

        if (!canRecord()) {
            recBtn.classList.add("hidden");
            hint.textContent = "Recording isn't available here (it needs HTTPS and a microphone). " +
                "Upload an audio file of the description instead.";
        }

        /* ---------- Small UI helpers ---------- */

        function setStatus(kind, text) {
            statusBox.className = `voice-status ${kind}`;
            statusBox.innerHTML = (kind === "working" ? `<span class="voice-spinner"></span>` : "") +
                `<span>${escapeHTML(text)}</span>`;
        }

        function clearStatus() {
            statusBox.className = "voice-status hidden";
            statusBox.innerHTML = "";
        }

        function clearReview() {
            reviewBox.className = "voice-review hidden";
            reviewBox.innerHTML = "";
        }

        function clearMarks() {
            form.querySelectorAll(".voice-filled, .voice-flag").forEach(input => {
                input.classList.remove("voice-filled", "voice-flag");
                input.removeAttribute("title");
            });
        }

        function setBusy(on) {
            uploadBtn.disabled = on;
            recBtn.disabled = on;
        }

        function setRecordingUI(on) {
            recBtn.classList.toggle("recording", on);
            recLabel.textContent = on ? "Stop · 0:00" : "Record";
            uploadBtn.disabled = on;
        }

        /* ---------- Recording ---------- */

        function cleanupStream() {
            stream?.getTracks().forEach(track => track.stop());
            stream = null;
        }

        function stopRecording() {
            if (recorder && recorder.state !== "inactive") recorder.stop();
        }

        async function startRecording() {
            clearStatus();
            clearReview();

            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (error) {
                setStatus("error", error.name === "NotAllowedError"
                    ? "Microphone access was blocked. Allow it in your browser, or upload an audio file instead."
                    : "No microphone was found. You can upload an audio file instead.");
                return;
            }

            const mime = pickMime();
            recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
            chunks = [];
            discard = false;

            recorder.ondataavailable = event => {
                if (event.data && event.data.size) chunks.push(event.data);
            };

            recorder.onstop = () => {
                clearInterval(timerId);
                cleanupStream();
                setRecordingUI(false);

                if (discard) {
                    discard = false;
                    return;
                }

                const type = recorder.mimeType || mime || "audio/webm";
                const blob = new Blob(chunks, { type });

                if (blob.size < 1000) {
                    setStatus("error", "That recording was empty. Please try again.");
                    return;
                }

                processAudio(blob, `recording.${extensionFor(type)}`);
            };

            recorder.start();
            startedAt = Date.now();
            setRecordingUI(true);

            timerId = setInterval(() => {
                const seconds = Math.floor((Date.now() - startedAt) / 1000);
                recLabel.textContent = `Stop · ${clock(seconds)}`;

                if (seconds >= MAX_RECORD_SECONDS) stopRecording();
            }, 250);
        }

        recBtn.addEventListener("click", () => {
            if (recorder && recorder.state === "recording") stopRecording();
            else startRecording();
        });

        /* ---------- Upload ---------- */

        uploadBtn.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", event => {
            const file = event.target.files?.[0];
            event.target.value = ""; // so the same file can be picked again

            if (!file) return;

            if (!looksLikeAudio(file)) {
                setStatus("error", "That doesn't look like an audio file.");
                return;
            }

            if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
                setStatus("error", `That file is larger than ${MAX_UPLOAD_MB} MB. Please use a shorter recording.`);
                return;
            }

            processAudio(file, file.name || "audio");
        });

        /* ---------- Send, wait, read the answer ---------- */

        async function readError(response, fallback) {
            const data = await response.json().catch(() => ({}));
            return errorMessage(data, response.status) || fallback;
        }

        // Checks the task until it has an answer. Returns the response body, or null if cancelled.
        async function waitForResult(taskId, my) {
            const began = Date.now();
            let failures = 0;

            while (Date.now() - began < MAX_WAIT_MS) {
                await sleep(POLL_MS);
                if (my !== runId) return null; // cancelled

                let response;

                try {
                    response = await api(statusPath(taskId));
                } catch (error) {
                    if (++failures >= 3) throw new Error("Lost the connection while waiting for the result.");
                    continue;
                }

                if (!response) return null; // sent to sign in
                if (!response.ok) {
                    throw new Error("The AI's answer couldn't be read. Please try again, or fill in the form by hand.");
                }

                failures = 0;
                const data = await response.json();

                if (data.result) return data;

                if (data.status === "Failed") {
                    console.error("Voice task failed:", data.developer_error);
                    throw new Error("The recording couldn't be processed. Please try again, or fill in the form by hand.");
                }

                setStatus("working", /STARTED|RETRY/i.test(String(data.status))
                    ? "Listening and reading the details…"
                    : "Waiting in the queue…");
            }

            throw new Error("This is taking too long. Please try again.");
        }

        async function processAudio(blob, filename) {
            const my = ++runId;

            setBusy(true);
            clearReview();
            setStatus("working", "Uploading the audio…");

            try {
                const body = new FormData();
                body.append("file", blob, filename); // the browser adds the multipart header itself

                const response = await api(INIT_PATH, { method: "POST", body });
                if (!response) return;
                if (!response.ok) throw new Error(await readError(response, "The audio couldn't be uploaded."));

                const { task_id: taskId } = await response.json();
                setStatus("working", "Waiting in the queue…");

                const data = await waitForResult(taskId, my);
                if (!data || my !== runId) return;

                showRecord(data.result, data.transcript);

            } catch (error) {
                if (my === runId) {
                    setStatus("error", error instanceof TypeError ? "Unable to connect to the server." : error.message);
                }
            } finally {
                if (my === runId) setBusy(false);
            }
        }

        /* ---------- Put the answer in the form ---------- */

        function fillForm(fields) {
            const filled = [];

            FIELD_KEYS.forEach(key => {
                const value = fields?.[key];
                const input = form.elements[key];

                if (value == null || value === "" || !input) return;

                input.value = String(value);
                input.classList.add("voice-filled");
                filled.push(key);
            });

            return filled;
        }

        function flagFields(record) {
            const reasons = new Map();

            (record.needs_review || []).forEach(note => reasons.set(note.field, note.reason));
            (record.missing_fields || []).forEach(key => {
                if (!reasons.has(key)) reasons.set(key, "Not heard in the recording.");
            });

            reasons.forEach((reason, key) => {
                const input = form.elements[key];
                if (!input) return;

                input.classList.remove("voice-filled");
                input.classList.add("voice-flag");
                input.setAttribute("title", reason);
            });
        }

        function renderReview(record, filled, transcript) {
            const notes = (record.needs_review || []).map(note => `
                <li><button type="button" class="voice-jump" data-field="${escapeHTML(note.field)}">${escapeHTML(LABELS[note.field] || note.field)}</button>
                    ${escapeHTML(note.reason)}</li>`);

            const notHeard = FIELD_KEYS.filter(key => !filled.includes(key));
            if (notHeard.length) {
                notes.push(`<li>Not heard: ${notHeard.map(key => escapeHTML(LABELS[key])).join(", ")}</li>`);
            }

            const parts = [];
            if (notes.length) parts.push(`<ul>${notes.join("")}</ul>`);
            if (record.follow_up_question) parts.push(`<p class="voice-follow">${escapeHTML(record.follow_up_question)}</p>`);
            if (transcript) {
                parts.push(`<details class="voice-heard"><summary>What I heard</summary><p>${escapeHTML(transcript)}</p></details>`);
            }

            if (!parts.length) return;

            reviewBox.className = "voice-review";
            reviewBox.innerHTML = parts.join("");
        }

        function showRecord(record, transcript) {
            clearMarks();

            if (record.status === "not_a_device_description") {
                setStatus("error", record.follow_up_question ||
                    "I couldn't hear a device description. Please try again, a bit closer to the microphone.");
                return;
            }

            const filled = fillForm(record.fields);
            flagFields(record);

            setStatus("ok", `Filled ${filled.length} of ${FIELD_KEYS.length} fields. ` +
                `Review them, fix anything that's wrong, then ${actionLabel}.`);

            renderReview(record, filled, transcript);
        }

        // Jump to a field named in the review list.
        reviewBox.addEventListener("click", event => {
            const jump = event.target.closest(".voice-jump");
            if (!jump) return;

            const input = form.elements[jump.dataset.field];
            if (!input) return;

            input.focus();
            input.scrollIntoView?.({ block: "center", behavior: "smooth" });
        });

        // Editing a field means the person has checked it, so its marks go away.
        form.addEventListener("input", event => {
            event.target.classList?.remove("voice-filled", "voice-flag");
            event.target.removeAttribute?.("title");
        });

        /* ---------- Public ---------- */

        // Call when the dialog opens or closes: stops a recording, cancels waiting, clears the messages.
        function reset() {
            runId++;

            if (recorder && recorder.state === "recording") {
                discard = true;
                stopRecording();
            }

            clearInterval(timerId);
            cleanupStream();
            setRecordingUI(false);
            setBusy(false);
            clearStatus();
            clearReview();
            clearMarks();
        }

        return { reset };
    }

    return { mount };
})();