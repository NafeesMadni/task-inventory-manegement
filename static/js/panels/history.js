/* =========================================================
   Device Portal – device history panel (admin only, mounted by devices.html)
   Animated tree:  device > ( details | Assignments > holders | Repairs > repairs )
   ========================================================= */

const HistoryPanel = (() => {
    const { $, api, escapeHTML, pretty } = Portal;
    const { statusTone, conditionTone, specChips } = DeviceUI;
    const { CHEV, plural } = TreeUI;

    // Route of the "all devices history" endpoint (relative to /api/v1).
    // Change it here if your router registers it under a different path.
    const DEVICES_HISTORY_PATH = "/device/history";

    let items = [];
    let tree = null; // expand/collapse state, created in bindEvents

    /* ---------- Helpers ---------- */

    function fmtDate(value) {
        const date = new Date(value);
        return !value || Number.isNaN(date.getTime()) ? "-" : date.toLocaleDateString();
    }

    function fmtDateTime(value) {
        const date = new Date(value);
        return !value || Number.isNaN(date.getTime()) ? "-" : date.toLocaleString();
    }

    function money(value) {
        const number = Number(value);
        return value == null || Number.isNaN(number)
            ? "-"
            : number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Username plus role badge.
    function person(user) {
        if (!user) return `<span class="muted">Unknown user</span>`;

        const role = String(user.role ?? "").toLowerCase();

        return `<strong>${escapeHTML(user.username)}</strong>` +
            (role ? ` <span class="role-badge ${escapeHTML(role)}">${escapeHTML(role)}</span>` : "");
    }

    function message(text, isError = false) {
        $("hi-list").innerHTML = `<div class="empty ${isError ? "error" : ""}">${escapeHTML(text)}</div>`;
    }

    /* ---------- Data ---------- */

    async function load() {
        message("Loading device history...");

        try {
            const response = await api(DEVICES_HISTORY_PATH);
            if (!response) return;
            if (response.status === 403) throw new Error("Only admins can view the device history.");
            if (!response.ok) throw new Error("Unable to load the device history.");

            items = (await response.json()).map(item => ({
                ...item,
                // Everything searchable in one string: the device, its holder and everyone who ever had or repaired it.
                _hay: [
                    item.device_info.id, item.device_info.name, item.device_info.brand,
                    item.device_info.serial_no, item.device_info.processor,
                    item.summary.current_holder?.username,
                    ...item.assignments.flatMap(a => [a.assigned_to?.username, a.assigned_by?.username]),
                    ...item.repairs.map(r => r.requested_by?.username),
                ].filter(v => v != null).join(" ").toLowerCase(),
                _updated: new Date(item.device_info.updated_at).getTime() || 0,
            }));

            fillStatuses();
            renderStats();
            render();

        } catch (error) {
            message(error.message, true);
        }
    }

    function fillStatuses() {
        const select = $("hi-status");
        const selected = select.value;
        const statuses = [...new Set(items.map(i => String(i.device_info.status)))].sort();

        select.innerHTML = `<option value="">All statuses</option>` +
            statuses.map(s => `<option value="${escapeHTML(s)}">${escapeHTML(pretty(s))}</option>`).join("");

        if (statuses.includes(selected)) select.value = selected;
    }

    function renderStats() {
        $("hi-s-total").textContent = items.length;
        $("hi-s-assigned").textContent = items.filter(i => i.summary.current_holder).length;
        $("hi-s-repair").textContent = items.filter(i => i.summary.under_repair).length;
        $("hi-s-repairs").textContent = items.reduce((n, i) => n + i.summary.total_repairs, 0);
    }

    /* ---------- Tree pieces ---------- */

    function infoLeaf(device) {
        return `
        <div class="tree-leaf multi branch" style="--i:0">
            <span class="leaf-dot info"></span>
            <div class="leaf-detail">
                <div class="spec-list">${specChips(device)}</div>
                <div class="muted step-sub" style="margin-top:8px">
                    ${escapeHTML(device.processor)} · Serial ${escapeHTML(device.serial_no)}
                </div>
                <div class="muted step-sub">
                    Purchased ${fmtDate(device.purchase_date)} for ${money(device.purchase_price)}
                    · Issued ${fmtDate(device.issued_at)}
                </div>
                <div class="muted step-sub">
                    Added ${fmtDate(device.created_at)} · Updated ${fmtDateTime(device.updated_at)}
                </div>
            </div>
        </div>`;
    }

    function assignmentLeaf(a, index) {
        const state = a.state || (a.returned_at ? "returned" : a.assigned_at ? "active" : "scheduled");

        const dot = state === "active" ? "active" : state === "scheduled" ? "info" : "ended";
        const pill = state === "active" ? `<span class="session-pill active">Active</span>`
            : state === "scheduled" ? `<span class="pill info">Scheduled</span>`
            : `<span class="pill">Returned</span>`;

        const dates = [
            `Scheduled ${fmtDate(a.scheduled_at)}`,
            a.assigned_at ? `Handed over ${fmtDate(a.assigned_at)}` : "",
            a.returned_at ? `Returned ${fmtDate(a.returned_at)}` : "",
        ].filter(Boolean).join(" · ");

        const conditions = [
            a.condition_on_issue ? `Condition on issue: ${pretty(a.condition_on_issue)}` : "",
            a.condition_on_return ? `on return: ${pretty(a.condition_on_return)}` : "",
        ].filter(Boolean).join(" · ");

        return `
        <div class="tree-leaf multi branch" style="--i:${index}">
            <span class="leaf-dot ${dot}"></span>
            <div class="step">
                <div class="step-line">
                    ${person(a.assigned_to)} ${pill}
                    <span class="muted">· ${a.request_id ? `request #${escapeHTML(a.request_id)}` : "assigned directly"}</span>
                </div>
                <div class="muted step-sub">${escapeHTML(dates)}</div>
                ${a.assigned_by || conditions ? `
                <div class="muted step-sub">
                    ${a.assigned_by ? `Assigned by ${person(a.assigned_by)}` : ""}
                    ${a.assigned_by && conditions ? " · " : ""}${escapeHTML(conditions)}
                </div>` : ""}
            </div>
        </div>`;
    }

    function repairTone(repair) {
        const v = pretty(repair.status);

        if (repair.is_active) return "warn";
        if (v.includes("complet")) return "ok";
        if (v.includes("cancel") || v.includes("reject")) return "bad";
        return "neutral";
    }

    function repairLeaf(r, index) {
        const tone = repairTone(r);

        const dates = [
            `Requested ${fmtDate(r.requested_at)}`,
            `Scheduled ${fmtDate(r.scheduled_at)}`,
            r.completed_at ? `Completed ${fmtDate(r.completed_at)}` : "",
        ].filter(Boolean).join(" · ");

        return `
        <div class="tree-leaf multi branch" style="--i:${index}">
            <span class="leaf-dot ${tone}"></span>
            <div class="step">
                <div class="step-line">
                    ${person(r.requested_by)}
                    <span class="pill ${tone === "neutral" ? "" : tone}">${escapeHTML(pretty(r.status))}</span>
                    <span class="muted">· request #${escapeHTML(r.request_id)}</span>
                </div>
                <div class="muted step-sub">${escapeHTML(dates)}</div>
                ${r.issue ? `<div class="muted remark">“${escapeHTML(r.issue)}”</div>` : ""}
                ${r.note ? `<div class="muted step-sub">Note: ${escapeHTML(r.note)}</div>` : ""}
            </div>
        </div>`;
    }

    // A collapsible group ("Assignments" / "Repairs") inside a device.
    function groupNode(key, index, title, badge, leaves) {
        const open = tree.openNodes.has(key);

        return `
        <div class="tree-node node-user branch${open ? " open" : ""}" data-key="${escapeHTML(key)}" style="--i:${index}">
            <div class="tree-row" role="button" tabindex="0" aria-expanded="${open}">
                ${CHEV}
                <span class="device-name">${escapeHTML(title)}</span>
                ${badge}
            </div>
            <div class="tree-children">
                <div class="tree-inner">${leaves}</div>
            </div>
        </div>`;
    }

    function deviceNode(item, forceOpen) {
        const { device_info: device, summary, assignments, repairs } = item;

        const key = `v:${device.id}`;
        const open = forceOpen || tree.openNodes.has(key);
        const activeRepairs = repairs.filter(r => r.is_active).length;

        const groups = [
            assignments.length ? groupNode(
                `a:${device.id}`, 1, "Assignments",
                `<span class="pill">${assignments.length}</span>` +
                (summary.current_holder ? `<span class="session-pill active">In use</span>` : ""),
                assignments.map((a, i) => assignmentLeaf(a, i)).join("")) : "",

            repairs.length ? groupNode(
                `r:${device.id}`, assignments.length ? 2 : 1, "Repairs",
                `<span class="pill">${repairs.length}</span>` +
                (activeRepairs ? `<span class="pill warn">${activeRepairs} active</span>` : ""),
                repairs.map((r, i) => repairLeaf(r, i)).join("")) : "",
        ].join("");

        return `
        <div class="tree-node node-day${open ? " open" : ""}" data-key="${escapeHTML(key)}">
            <div class="tree-row" role="button" tabindex="0" aria-expanded="${open}" style="flex-wrap:wrap;row-gap:6px">
                ${CHEV}
                <span class="device-name">${escapeHTML(device.name)}</span>
                <span class="device-sub" style="margin:0">${escapeHTML(device.brand)} · #${escapeHTML(device.id)}</span>
                <span class="pill ${statusTone(device.status)}">${escapeHTML(pretty(device.status))}</span>
                <span class="pill ${conditionTone(device.condition)}">${escapeHTML(pretty(device.condition))}</span>
                ${summary.under_repair ? `<span class="pill warn">Under repair</span>` : ""}
                ${summary.current_holder
                    ? `<span class="muted">with</span> ${person(summary.current_holder)}`
                    : ""}
                <span class="tree-meta">${plural(summary.total_assignments, "assignment")} · ${plural(summary.total_repairs, "repair")}</span>
            </div>
            <div class="tree-children">
                <div class="tree-inner">
                    ${infoLeaf(device)}
                    ${groups}
                </div>
            </div>
        </div>`;
    }

    /* ---------- Render ---------- */

    function render() {
        const search = $("hi-search").value.trim().toLowerCase();
        const status = $("hi-status").value;
        const activity = $("hi-activity").value;
        const sort = $("hi-sort").value;

        const visible = items.filter(item => {
            const { device_info: d, summary: s } = item;

            if (search && !item._hay.includes(search)) return false;
            if (status && String(d.status) !== status) return false;

            if (activity === "assigned" && !s.current_holder) return false;
            if (activity === "repair" && !s.under_repair) return false;
            if (activity === "repaired" && s.total_repairs === 0) return false;
            if (activity === "never" && s.total_assignments > 0) return false;

            return true;
        });

        visible.sort((a, b) => {
            if (sort === "updated") return b._updated - a._updated;
            if (sort === "repairs") return b.summary.total_repairs - a.summary.total_repairs;
            if (sort === "assignments") return b.summary.total_assignments - a.summary.total_assignments;

            return String(a.device_info.name).localeCompare(String(b.device_info.name), undefined, { sensitivity: "base" });
        });

        $("hi-count").textContent = visible.length === items.length
            ? plural(items.length, "device")
            : `${visible.length} of ${items.length} devices`;

        if (!items.length) {
            message("No devices in the inventory yet.");
            return;
        }

        if (!visible.length) {
            message("No devices match your filters.");
            return;
        }

        // While searching, open each matching device so the hit is visible (groups stay as you left them).
        $("hi-list").innerHTML = visible.map(item => deviceNode(item, Boolean(search))).join("");
    }

    function bindEvents() {
        $("hi-refresh").addEventListener("click", load);

        $("hi-search").addEventListener("input", render);
        ["hi-status", "hi-activity", "hi-sort"].forEach(id => $(id).addEventListener("change", render));

        $("hi-clear").addEventListener("click", () => {
            $("hi-search").value = "";
            $("hi-status").value = "";
            $("hi-activity").value = "";
            $("hi-sort").value = "name";
            render();
        });

        tree = TreeUI.create($("hi-list"));

        $("hi-expand").addEventListener("click", () => tree.setAll(true));
        $("hi-collapse").addEventListener("click", () => tree.setAll(false));
    }

    // Called once, the first time the panel is shown.
    async function mount() {
        bindEvents();
        await load();
    }

    return { mount };
})();