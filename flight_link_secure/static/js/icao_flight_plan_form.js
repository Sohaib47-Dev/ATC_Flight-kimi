/**
 * Structured ICAO flight plan form: live FPL build, hidden raw_flight_plan sync,
 * optional server parse (apply from raw / import).
 */
(function () {
  "use strict";

  function fourDigits(s) {
    const d = String(s || "").replace(/\D/g, "");
    if (!d) return "0000";
    return (d + "0000").slice(0, 4);
  }

  function val(root, name) {
    const el = root.querySelector('[data-fpl-field="' + name + '"]');
    return el ? el.value : "";
  }

  function setVal(root, name, value) {
    const el = root.querySelector('[data-fpl-field="' + name + '"]');
    if (el) el.value = value != null ? String(value) : "";
  }

  var ICAO_AD_RE = /^[A-Z]{4}$/;
  var CALLSIGN_AIRLINE_RE = /^[A-Z]{3}[A-Z0-9]{1,4}$/;
  var CALLSIGN_GA_N_RE = /^N\d{1,5}[A-Z]{0,2}$/;
  var CALLSIGN_GA_REG_RE = /^[A-Z]{1,2}[A-Z0-9]{2,6}$/;
  var AC_TYPE_RE = /^[A-Z][A-Z0-9]{1,3}$/;

  function isValidCallsign(value) {
    return (
      CALLSIGN_AIRLINE_RE.test(value) ||
      CALLSIGN_GA_N_RE.test(value) ||
      CALLSIGN_GA_REG_RE.test(value)
    );
  }

  function validateRequired(root) {
    var errs = [];
    var cs = (val(root, "callsign") || "").trim().toUpperCase();
    if (!isValidCallsign(cs)) errs.push("callsign (ICAO airline or GA format)");
    var ac = (val(root, "aircraft_type") || "").trim().toUpperCase();
    if (!AC_TYPE_RE.test(ac) || ac === "ZZZZ") errs.push("aircraft type (2-4 ICAO designator)");
    var dep = (val(root, "departure_aerodrome") || "").trim().toUpperCase();
    if (!ICAO_AD_RE.test(dep)) errs.push("departure (4-letter ICAO)");
    var dest = (val(root, "destination_aerodrome") || "").trim().toUpperCase();
    if (!ICAO_AD_RE.test(dest)) errs.push("destination (4-letter ICAO)");
    var route = (val(root, "route") || "").trim();
    if (!route.length) errs.push("route");
    return errs;
  }

  function buildRawFromForm(root) {
    const cs = (val(root, "callsign") || "").trim().toUpperCase();
    const fr = (val(root, "flight_rules") || "I").trim().toUpperCase().charAt(0) || "I";
    const tf = (val(root, "type_of_flight") || "S").trim().toUpperCase().charAt(0) || "S";
    const ac = (val(root, "aircraft_type") || "").trim().toUpperCase();
    const wtc = (val(root, "wake_turbulence") || "M").trim().toUpperCase().charAt(0) || "M";
    const eq = (val(root, "equipment") || "").trim();
    const dep = (val(root, "departure_aerodrome") || "").trim().toUpperCase().slice(0, 4);
    const depT = fourDigits(val(root, "departure_time_utc"));
    const spd = (val(root, "cruise_speed") || "N0450").trim().toUpperCase() || "N0450";
    const lvl = (val(root, "flight_level") || "F350").trim().toUpperCase() || "F350";
    const route = (val(root, "route") || "").trim();
    const dest = (val(root, "destination_aerodrome") || "").trim().toUpperCase().slice(0, 4);
    const destT = fourDigits(val(root, "destination_time_utc"));
    let altSuf = (val(root, "alternate_suffix") || "").trim();
    if (altSuf && altSuf.charAt(0) !== " ") altSuf = " " + altSuf;
    const f18 = (val(root, "field_18") || "").trim();
    const other = (val(root, "other_info") || "").trim();

    const lines = ["(FPL-" + cs + "-" + fr + tf];
    if (eq) lines.push("-" + ac + "/" + wtc + "-" + eq);
    else lines.push("-" + ac + "/" + wtc);
    lines.push("-" + dep + depT);
    lines.push(("-" + spd + lvl + " " + route).trimEnd());
    lines.push(("-" + dest + destT + altSuf).trimEnd());
    if (f18) {
      f18.split(/\r?\n/).forEach(function (block) {
        const b = block.trim();
        if (!b) return;
        lines.push(b.charAt(0) === "-" ? b : "-" + b);
      });
    }
    if (other) {
      other.split(/\r?\n/).forEach(function (block) {
        const b = block.trim();
        if (!b) return;
        lines.push(b.charAt(0) === "-" ? b : "-" + b);
      });
    }
    lines.push(")");
    return lines.join("\n");
  }

  function applyFields(root, fields) {
    if (!fields) return;
    Object.keys(fields).forEach(function (k) {
      setVal(root, k, fields[k] != null ? fields[k] : "");
    });
  }

  function initIcaoFlightPlanForm(opts) {
    const form = document.querySelector(opts.formSelector);
    if (!form) return;

    const root = form.querySelector(".icao-fpl-structured") || form;
    const hiddenRaw = form.querySelector("#raw_flight_plan");
    const preview = form.querySelector("#icao_fpl_preview");
    const rawEditor = form.querySelector("#icao_raw_editor");
    const parserStatus = form.querySelector("#icao_parser_status");
    const mode = opts.mode || "add";
    const planId = opts.planId != null ? String(opts.planId) : "";
    const apiUrl = opts.apiParseUrl || "";
    const csrfToken = opts.csrfToken || "";
    const draftKey =
      mode === "edit" && planId
        ? "flight_link_icao_fpl_edit_" + planId
        : "flight_link_icao_fpl_draft_add";

    function syncFromForm() {
      var missing = validateRequired(root);
      if (missing.length) {
        if (hiddenRaw) hiddenRaw.value = "";
        if (preview) {
          preview.textContent =
            "Complete required fields: " + missing.join(", ") + ".";
        }
        return;
      }
      const text = buildRawFromForm(root);
      if (hiddenRaw) hiddenRaw.value = text;
      if (preview) preview.textContent = text;
      if (rawEditor && document.activeElement !== rawEditor) rawEditor.value = text;
    }

    let parserCheckTimer = null;
    function scheduleParserCheck() {
      if (parserCheckTimer) clearTimeout(parserCheckTimer);
      parserCheckTimer = setTimeout(function () {
        checkParserServer(hiddenRaw ? hiddenRaw.value : "");
      }, 400);
    }

    function checkParserServer(rawText) {
      if (!apiUrl) return;
      if (!rawText || !String(rawText).trim()) {
        setParserIncomplete("Parser: complete required fields first");
        return;
      }
      fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ raw_flight_plan: rawText || "" }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (!data) return;
          setParserStatus(data.parser_ok, data.parser_errors || []);
        })
        .catch(function () {
          setParserStatus(false, ["Parser check failed"]);
        });
    }

    function setParserStatus(parserOk, errs) {
      if (!parserStatus) return;
      parserStatus.classList.remove("text-success", "text-warning", "text-danger", "text-secondary");
      if (parserOk) {
        parserStatus.textContent = "Parser: OK (matches FlightPlanParser)";
        parserStatus.classList.add("text-success");
      } else {
        const e = (errs && errs.length) ? errs.join("; ") : "Unknown";
        parserStatus.textContent = "Parser: " + e;
        parserStatus.classList.add("text-danger");
      }
    }

    function setParserIncomplete(msg) {
      if (!parserStatus) return;
      parserStatus.classList.remove("text-success", "text-warning", "text-danger");
      parserStatus.classList.add("text-secondary");
      parserStatus.textContent = msg || "Parser: complete required fields first";
    }

    form.querySelectorAll("[data-fpl-field]").forEach(function (el) {
      el.addEventListener("input", function () {
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          el.value = String(el.value || "").toUpperCase();
        }
        syncFromForm();
        scheduleParserCheck();
      });
      el.addEventListener("change", function () {
        syncFromForm();
        scheduleParserCheck();
      });
    });

    let parseTimer = null;
    if (rawEditor) {
      rawEditor.addEventListener("input", function () {
        if (parseTimer) clearTimeout(parseTimer);
        parseTimer = setTimeout(function () {
          applyFromRawText(rawEditor.value, false);
        }, 450);
      });
    }

    function applyFromRawText(rawText, showAlert) {
      if (!apiUrl) return;
      fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ raw_flight_plan: rawText }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (!data || !data.fields) return;
          applyFields(root, data.fields);
          if (mode === "add") {
            const cs = data.fields.callsign || "";
            const csInput = form.querySelector('input[name="callsign"]');
            if (csInput && cs) csInput.value = cs;
          }
          syncFromForm();
          setParserStatus(data.parser_ok, data.parser_errors || []);
          if (showAlert && data.notes && data.notes.length) {
            /* non-blocking */
            console.info("FPL form parse notes:", data.notes);
          }
        })
        .catch(function () {
          setParserStatus(false, ["Parse request failed"]);
        });
    }

    const btnCopy = form.querySelector("#icao_btn_copy");
    if (btnCopy) {
      btnCopy.addEventListener("click", function () {
        const t = hiddenRaw ? hiddenRaw.value : "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(t).catch(function () {});
        }
      });
    }

    const btnClear = form.querySelector("#icao_btn_clear");
    if (btnClear) {
      btnClear.addEventListener("click", function () {
        if (!confirm("Reset all flight plan fields to defaults?")) return;
        const defaults = opts.defaults || {};
        Object.keys(defaults).forEach(function (k) {
          setVal(root, k, defaults[k]);
        });
        if (mode === "add") {
          const csInput = form.querySelector('input[name="callsign"]');
          if (csInput) csInput.value = "";
        }
        syncFromForm();
        checkParserServer(hiddenRaw ? hiddenRaw.value : "");
      });
    }

    const btnApplyRaw = form.querySelector("#icao_btn_apply_raw");
    if (btnApplyRaw && rawEditor) {
      btnApplyRaw.addEventListener("click", function () {
        applyFromRawText(rawEditor.value, true);
      });
    }

    const btnSaveDraft = form.querySelector("#icao_btn_save_draft");
    if (btnSaveDraft) {
      btnSaveDraft.addEventListener("click", function () {
        try {
          const payload = { fields: {}, raw: hiddenRaw ? hiddenRaw.value : "" };
          root.querySelectorAll("[data-fpl-field]").forEach(function (el) {
            const k = el.getAttribute("data-fpl-field");
            if (k) payload.fields[k] = el.value;
          });
          if (mode === "add") {
            const csInput = form.querySelector('input[name="callsign"]');
            if (csInput) payload.callsign = csInput.value;
          }
          localStorage.setItem(draftKey, JSON.stringify(payload));
        } catch (e) {}
      });
    }

    const btnLoadDraft = form.querySelector("#icao_btn_load_draft");
    if (btnLoadDraft) {
      btnLoadDraft.addEventListener("click", function () {
        try {
          const s = localStorage.getItem(draftKey);
          if (!s) return;
          const payload = JSON.parse(s);
          if (payload.fields) applyFields(root, payload.fields);
          if (mode === "add" && payload.callsign) {
            const csInput = form.querySelector('input[name="callsign"]');
            if (csInput) csInput.value = payload.callsign;
          }
          if (payload.raw && rawEditor) rawEditor.value = payload.raw;
          syncFromForm();
          checkParserServer(hiddenRaw ? hiddenRaw.value : "");
        } catch (e) {}
      });
    }

    form.addEventListener("submit", function (e) {
      syncFromForm();
      if (!form.checkValidity()) {
        e.preventDefault();
        form.reportValidity();
        return;
      }
      var miss = validateRequired(root);
      if (miss.length) {
        e.preventDefault();
        window.alert("Please complete: " + miss.join(", ") + ".");
        return;
      }
      if (!hiddenRaw || !String(hiddenRaw.value).trim()) {
        e.preventDefault();
        window.alert("ICAO message is empty. Fill callsign, aircraft type, departure, destination, and route.");
        return;
      }
    });

    syncFromForm();
    checkParserServer(hiddenRaw ? hiddenRaw.value : "");
  }

  window.initIcaoFlightPlanForm = initIcaoFlightPlanForm;
})();
