/* =========================================================
   Device Portal – shared device helpers
   Used by the Devices, My Devices and Requests panels. Load after shell.js.
   ========================================================= */

const DeviceUI = (() => {
    const { api, pretty } = Portal;

    // Route of the "devices assigned to me" endpoint (relative to /api/v1).
    // Change it here if your router registers it under a different path.
    const MY_DEVICES_PATH = "/device/my-devices";

    // Status / condition values are matched by keyword, so this works whatever your enums are called.
    function statusTone(value) {
        const v = pretty(value);
        if (v.includes("avail")) return "ok";
        if (v.includes("reserv") || v.includes("assign") || v.includes("issue")) return "info";
        if (v.includes("repair")) return "warn";
        if (v.includes("retire") || v.includes("lost") || v.includes("damag")) return "bad";
        return "neutral";
    }

    function conditionTone(value) {
        const v = pretty(value);
        if (v.includes("new") || v.includes("good") || v.includes("excellent")) return "ok";
        if (v.includes("fair") || v.includes("used")) return "warn";
        if (v.includes("poor") || v.includes("bad") || v.includes("damag") || v.includes("broken")) return "bad";
        return "neutral";
    }

    // When the device was added to the inventory (a full date + time).
    // The API now returns created_at; issued_at is read only as a fallback while the backend rename rolls out.
    function addedAt(device) {
        return device.created_at ?? device.issued_at ?? null;
    }

    // "16 GB RAM" "512 GB SSD" ... as small chips (empty values are skipped).
    function specChips(device) {
        return [
            device.ram_gb ? `${device.ram_gb} GB RAM` : "",
            device.ssd_gb ? `${device.ssd_gb} GB SSD` : "",
            device.hdd_gb ? `${device.hdd_gb} GB HDD` : "",
        ].filter(Boolean).map(s => `<span class="spec">${s}</span>`).join("");
    }

    /* ---------- My devices ---------- */

    let mine = null;    // cached result, shared by the My Devices tab and the repair picker
    let pending = null; // request in flight, so simultaneous callers share one call

    // The API returns [{ device_info, assigned_at, condition_on_issue }].
    // This flattens each item to { ...device_info, assigned_at, condition_on_issue }.
    function loadMine(force = false) {
        if (mine && !force) return Promise.resolve(mine);
        if (pending && !force) return pending;

        pending = (async () => {
            const response = await api(MY_DEVICES_PATH);

            if (!response) return []; // redirected to sign in
            if (!response.ok) throw new Error("Unable to load your devices.");

            mine = (await response.json()).map(item => ({
                ...item.device_info,
                assigned_at: item.assigned_at,
                condition_on_issue: item.condition_on_issue,
            }));

            return mine;
        })().finally(() => { pending = null; });

        return pending;
    }

    function invalidateMine() {
        mine = null;
    }

    return { statusTone, conditionTone, specChips, addedAt, loadMine, invalidateMine };
})();