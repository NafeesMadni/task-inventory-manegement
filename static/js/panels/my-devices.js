/* =========================================================
   Device Portal – "My Devices" panel (mounted by devices.html)
   Devices currently assigned to the signed-in supervisor / developer.
   ========================================================= */

const MyDevicesPanel = (() => {
    const { $, escapeHTML, pretty } = Portal;
    const { conditionTone, specChips, loadMine } = DeviceUI;

    let devices = [];
    let meId = null; // the signed-in user

    function formatDate(value) {
        const date = new Date(value);
        return !value || Number.isNaN(date.getTime()) ? "-" : date.toLocaleDateString();
    }

    function tableMessage(text, isError = false) {
        $("md-table").innerHTML =
            `<tr><td colspan="5" class="page-note ${isError ? "error" : ""}">${escapeHTML(text)}</td></tr>`;
    }

    async function load(force = false) {
        tableMessage("Loading your devices...");

        try {
            // Most recently assigned first.
            devices = [...await loadMine(force)].sort(
                (a, b) => new Date(b.assigned_at) - new Date(a.assigned_at));

            render();

        } catch (error) {
            tableMessage(error.message, true);
        }
    }

    function render() {
        const search = $("md-search").value.trim().toLowerCase();

        const visible = devices.filter(d =>
            !search || [d.id, d.name, d.brand, d.processor].join(" ").toLowerCase().includes(search));

        $("md-count").textContent = visible.length === devices.length
            ? `${devices.length} device${devices.length === 1 ? "" : "s"}`
            : `${visible.length} of ${devices.length} devices`;

        if (!devices.length) {
            tableMessage("No devices are assigned to you right now. You can ask for one from the Requests tab.");
            return;
        }

        if (!visible.length) {
            tableMessage("No devices match your search.");
            return;
        }

        $("md-table").innerHTML = visible.map(device => `
            <tr>
                <td>
                    <div class="device-name">${escapeHTML(device.name)}</div>
                    <div class="device-sub">${escapeHTML(device.brand)} · #${escapeHTML(device.id)}</div>
                </td>
                <td>
                    <div class="device-sub" style="margin:0 0 6px">${escapeHTML(device.processor)}</div>
                    <div class="spec-list">${specChips(device)}</div>
                </td>
                <td><span class="pill ${conditionTone(device.condition)}">${escapeHTML(pretty(device.condition))}</span></td>
                <td>
                    <div>${formatDate(device.assigned_at)}</div>
                    ${device.condition_on_issue
                        ? `<div class="device-sub">Issued as ${escapeHTML(pretty(device.condition_on_issue))}</div>`
                        : ""}
                </td>
                <td>
                    <div class="actions">
                        <button class="btn btn-sm" data-repair="${escapeHTML(device.id)}">Request repair</button>
                        <button class="btn btn-sm" data-return="${escapeHTML(device.id)}">Return</button>
                    </div>
                </td>
            </tr>`).join("");
    }

    function bindEvents() {
        $("md-refresh").addEventListener("click", () => load(true));
        $("md-search").addEventListener("input", render);

        // The hub (devices.html) switches to the Requests tab and opens the repair dialog.
        $("md-table").addEventListener("click", event => {
            const give = event.target.closest("button[data-return]");

            if (give) {
                const device = devices.find(d => d.id === Number(give.dataset.return));
                if (!device) return;

                // A holder handing their own device back; the server records it as a return.
                AccessUI.open({
                    mode: "return",
                    deviceId: device.id,
                    deviceName: device.name,
                    holderId: meId,
                    holderName: "you",
                    onDone: () => load(true),
                });
                return;
            }

            const button = event.target.closest("button[data-repair]");
            if (!button) return;

            document.dispatchEvent(new CustomEvent("portal:request-repair", {
                detail: { deviceId: Number(button.dataset.repair) },
            }));
        });
    }

    // Called once, the first time the panel is shown.
    async function mount(session) {
        meId = session.user.id;
        bindEvents();
        await load();
    }

    return { mount };
})();