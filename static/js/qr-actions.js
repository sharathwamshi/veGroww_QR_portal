/* =====================================================================
   qr-actions.js — shared QR viewer, copy and download behaviour.
   Wired by data attributes, so every module (Image QR, UPI QR, ID cards)
   uses the same viewer with no per-page JavaScript.

   Markup contract:
     <button class="qr-open"
             data-qr-src="/media/qr/xyz.png"        (required)
             data-qr-download="/image-qr/1/qr"       (required)
             data-qr-title="Testing"
             data-qr-kind="Image QR"
             data-qr-link="https://tinyurl.com/..."  (value encoded in the QR)
             data-qr-link-label="Encoded link">
   ===================================================================== */
(function () {
  "use strict";

  var modal, dialogTitle, dialogKind, stageImg, linkBox, linkLabel, linkValue,
      btnDownload, btnCopyImage, btnCopyLink, lastFocused;

  var current = { src: "", download: "", title: "", link: "" };

  /* ------------------------------------------------------------------
     Toasts
     ------------------------------------------------------------------ */
  function toast(message, isError) {
    var stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    var el = document.createElement("div");
    el.className = "toast" + (isError ? " is-error" : "");
    el.setAttribute("role", "status");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(function () {
      el.classList.add("is-out");
      setTimeout(function () { el.remove(); }, 220);
    }, 2600);
  }

  /* ------------------------------------------------------------------
     Clipboard: text
     ------------------------------------------------------------------ */
  function copyText(text) {
    if (!text) {
      toast("Nothing to copy for this code.", true);
      return;
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () { toast("Link copied"); },
        function () { legacyCopyText(text); }
      );
    } else {
      legacyCopyText(text);
    }
  }

  // http:// on a LAN IP is not a secure context, so navigator.clipboard is
  // unavailable there. Fall back to a hidden textarea + execCommand.
  function legacyCopyText(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-1000px";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    toast(ok ? "Link copied" : "Couldn't copy — select the link and copy manually.", !ok);
  }

  /* ------------------------------------------------------------------
     Clipboard: the QR image itself (PNG)
     ------------------------------------------------------------------ */
  function copyImage(src) {
    if (!src) { return; }

    if (!(navigator.clipboard && window.ClipboardItem && window.isSecureContext)) {
      toast("Image copy needs HTTPS or localhost — use Download instead.", true);
      return;
    }

    fetch(src, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) { throw new Error("fetch failed"); }
        return res.blob();
      })
      .then(function (blob) {
        // Clipboard only accepts image/png; re-encode anything else via canvas.
        if (blob.type === "image/png") { return blob; }
        return toPngBlob(blob);
      })
      .then(function (pngBlob) {
        var item = new window.ClipboardItem({ "image/png": pngBlob });
        return navigator.clipboard.write([item]);
      })
      .then(function () { toast("QR image copied"); })
      .catch(function () {
        toast("Couldn't copy the image — use Download instead.", true);
      });
  }

  function toPngBlob(blob) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(blob);
      var img = new Image();
      img.onload = function () {
        var canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext("2d").drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        canvas.toBlob(function (out) {
          out ? resolve(out) : reject(new Error("encode failed"));
        }, "image/png");
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("load failed")); };
      img.src = url;
    });
  }

  /* ------------------------------------------------------------------
     Modal
     ------------------------------------------------------------------ */
  function openModal(data) {
    current = data;
    dialogTitle.textContent = data.title || "QR code";
    dialogKind.textContent = data.kind || "QR code";
    stageImg.src = data.src;
    stageImg.alt = "QR code for " + (data.title || "this item");
    btnDownload.href = data.download;

    if (data.link) {
      linkLabel.textContent = data.linkLabel || "Encoded link";
      linkValue.textContent = data.link;
      linkBox.style.display = "";
      btnCopyLink.disabled = false;
    } else {
      linkBox.style.display = "none";
      btnCopyLink.disabled = true;
    }

    lastFocused = document.activeElement;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    btnDownload.focus();
  }

  function closeModal() {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    stageImg.removeAttribute("src");
    if (lastFocused && lastFocused.focus) { lastFocused.focus(); }
  }

  // Keep tab focus inside the dialog while it's open.
  function trapFocus(e) {
    if (e.key !== "Tab" || !modal.classList.contains("open")) { return; }
    var focusables = modal.querySelectorAll(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) { return; }
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  /* ------------------------------------------------------------------
     Listing filter
     ------------------------------------------------------------------ */
  function initFilter() {
    var input = document.querySelector("[data-filter-input]");
    if (!input) { return; }
    var scope = document.querySelector("[data-filter-scope]");
    var counter = document.querySelector("[data-filter-count]");
    var empty = document.querySelector("[data-filter-empty]");
    if (!scope) { return; }

    var rows = Array.prototype.slice.call(scope.querySelectorAll("[data-filter-text]"));
    var total = rows.length;

    function apply() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var match = !q || row.getAttribute("data-filter-text").toLowerCase().indexOf(q) !== -1;
        row.style.display = match ? "" : "none";
        if (match) { shown++; }
      });
      if (counter) {
        counter.textContent = q
          ? shown + " of " + total + " shown"
          : total + (total === 1 ? " item" : " items");
      }
      if (empty) { empty.style.display = shown === 0 ? "" : "none"; }
    }

    input.addEventListener("input", apply);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { input.value = ""; apply(); }
    });
    apply();
  }


  /* ------------------------------------------------------------------
     Collapsible sidebar
     ------------------------------------------------------------------ */
  var NAV_KEY = "vegroww.nav.collapsed";

  function initSidebar() {
    var shell = document.querySelector(".app-shell");
    var toggle = document.querySelector("[data-sidebar-toggle]");
    if (!shell || !toggle) { return; }

    function paint(collapsed) {
      shell.classList.toggle("nav-collapsed", collapsed);
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      var text = collapsed ? "Expand menu" : "Collapse menu";
      toggle.setAttribute("aria-label", text);
      toggle.setAttribute("title", text);
    }

    var stored = false;
    try { stored = localStorage.getItem(NAV_KEY) === "1"; } catch (e) { stored = false; }
    paint(stored);

    toggle.addEventListener("click", function () {
      var collapsed = !shell.classList.contains("nav-collapsed");
      paint(collapsed);
      try { localStorage.setItem(NAV_KEY, collapsed ? "1" : "0"); } catch (e) { /* private mode */ }
    });
  }

  /* ------------------------------------------------------------------
     Accordion sections (vCard builder)
     ------------------------------------------------------------------ */
  function initAccordions() {
    document.querySelectorAll("[data-accordion-toggle]").forEach(function (head) {
      head.addEventListener("click", function () {
        var section = head.closest("[data-accordion]");
        if (!section) { return; }
        var open = section.hasAttribute("open");
        if (open) {
          section.removeAttribute("open");
        } else {
          section.setAttribute("open", "");
        }
        head.setAttribute("aria-expanded", open ? "false" : "true");
      });
    });
  }

  /* ------------------------------------------------------------------
     Repeatable rows (phones, emails, websites, socials)
     ------------------------------------------------------------------ */
  function syncEmpty(group) {
    var rows = group.querySelector("[data-repeat-rows]");
    var empty = group.querySelector("[data-repeat-empty]");
    if (empty) { empty.style.display = rows.children.length ? "none" : ""; }
  }

  function initRepeats() {
    document.querySelectorAll("[data-repeat-group]").forEach(syncEmpty);

    document.addEventListener("click", function (e) {
      var addBtn = e.target.closest("[data-repeat-add]");
      if (addBtn) {
        e.preventDefault();
        var group = addBtn.closest("[data-repeat-group]");
        var tpl = group.querySelector("[data-repeat-template]");
        var rows = group.querySelector("[data-repeat-rows]");
        rows.appendChild(tpl.content.cloneNode(true));
        syncEmpty(group);
        var inputs = rows.lastElementChild.querySelectorAll("input, select");
        if (inputs.length) { inputs[0].focus(); }
        return;
      }

      var removeBtn = e.target.closest("[data-repeat-remove]");
      if (removeBtn) {
        e.preventDefault();
        var grp = removeBtn.closest("[data-repeat-group]");
        removeBtn.closest(".repeat-row").remove();
        syncEmpty(grp);
      }
    });
  }

  /* ------------------------------------------------------------------
     Colour palette + live image preview (vCard builder)
     ------------------------------------------------------------------ */
  function initDesignControls() {
    var swatches = document.querySelectorAll("[data-palette]");
    var primary = document.getElementById("primary_color");
    var secondary = document.getElementById("secondary_color");

    function markActive() {
      if (!primary || !secondary) { return; }
      swatches.forEach(function (sw) {
        var pair = sw.getAttribute("data-palette").split("|");
        sw.classList.toggle(
          "is-active",
          pair[0].toLowerCase() === primary.value.toLowerCase() &&
          pair[1].toLowerCase() === secondary.value.toLowerCase()
        );
      });
    }

    swatches.forEach(function (sw) {
      sw.addEventListener("click", function () {
        var pair = sw.getAttribute("data-palette").split("|");
        if (!primary || !secondary) { return; }
        primary.value = pair[0];
        secondary.value = pair[1];
        var pp = document.getElementById("primary_color_picker");
        var sp = document.getElementById("secondary_color_picker");
        if (pp) { pp.value = pair[0]; }
        if (sp) { sp.value = pair[1]; }
        markActive();
      });
    });

    // Keep the native colour picker and the hex text field in step.
    document.querySelectorAll("[data-color-picker]").forEach(function (picker) {
      var target = document.getElementById(picker.getAttribute("data-color-picker"));
      if (!target) { return; }
      picker.addEventListener("input", function () {
        target.value = picker.value.toUpperCase();
        markActive();
      });
      target.addEventListener("input", function () {
        if (/^#[0-9a-fA-F]{6}$/.test(target.value)) {
          picker.value = target.value;
          markActive();
        }
      });
    });

    markActive();

    var imageInput = document.querySelector("[data-image-input]");
    var preview = document.querySelector("[data-image-preview]");
    if (imageInput && preview) {
      imageInput.addEventListener("change", function () {
        var file = imageInput.files && imageInput.files[0];
        if (!file) { return; }
        var url = URL.createObjectURL(file);
        preview.innerHTML = '<img alt="Selected profile image">';
        preview.querySelector("img").src = url;
      });
    }
  }


  /* ------------------------------------------------------------------
     Invitation builder: the form reshapes itself around the chosen event
     ------------------------------------------------------------------ */
  function initInviteForm() {
    var form = document.querySelector("[data-invite-form]");
    if (!form) { return; }

    var radios = form.querySelectorAll("[data-event-radio]");
    var secondaryBlock = form.querySelector("[data-secondary-block]");
    var pickFirst = form.querySelector("[data-pick-first]");
    var primaryHeading = form.querySelector("[data-primary-heading]");

    function applyEvent(radio) {
      var key = radio.value;
      var twoSessions = radio.getAttribute("data-two-sessions") === "1";

      form.querySelectorAll(".event-option").forEach(function (opt) {
        opt.classList.toggle("is-selected", opt.contains(radio));
      });

      // Show only the chosen event's host fields, and make sure hidden
      // inputs are neither required nor submitted with stale values.
      form.querySelectorAll("[data-host-fields]").forEach(function (group) {
        var active = group.getAttribute("data-host-fields") === key;
        group.hidden = !active;
        group.querySelectorAll("input").forEach(function (input) {
          input.disabled = !active;
          if (active) {
            input.required = input.getAttribute("data-required-when") === "1";
          } else {
            input.required = false;
          }
        });
      });

      if (pickFirst) { pickFirst.hidden = true; }

      // Step-wise flow: collapse the occasion step and open the next one,
      // so the long picker doesn't stay in the way after choosing.
      var occasionSection = radio.closest("[data-accordion]");
      if (occasionSection) {
        occasionSection.classList.add("is-done");
        var summary = occasionSection.querySelector("[data-accordion-summary]");
        if (summary) {
          var nameEl = radio.parentElement.querySelector(".event-name");
          summary.textContent = nameEl ? nameEl.textContent.trim() : key;
          summary.hidden = false;
        }
        var sub = occasionSection.querySelector(".accordion-sub");
        if (sub) { sub.hidden = true; }

        // Only advance on a real click, not on the initial page render.
        if (radio.dataset.userPicked === "1") {
          occasionSection.removeAttribute("open");
          var head = occasionSection.querySelector("[data-accordion-toggle]");
          if (head) { head.setAttribute("aria-expanded", "false"); }

          var next = occasionSection.nextElementSibling;
          while (next && !next.hasAttribute("data-accordion")) {
            next = next.nextElementSibling;
          }
          if (next) {
            next.setAttribute("open", "");
            var nextHead = next.querySelector("[data-accordion-toggle]");
            if (nextHead) { nextHead.setAttribute("aria-expanded", "true"); }
            next.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
      }

      if (secondaryBlock) {
        secondaryBlock.hidden = !twoSessions;
        secondaryBlock.querySelectorAll("input").forEach(function (input) {
          input.disabled = !twoSessions;
          var needed = twoSessions &&
            (input.name === "secondary_date" || input.name === "secondary_time");
          input.required = needed;
        });
      }

      if (primaryHeading) {
        primaryHeading.textContent = twoSessions ? "Ceremony" : "Event";
      }

      // Only recolour when the user hasn't already picked their own.
      if (!form.dataset.colorTouched) {
        var p = document.getElementById("primary_color");
        var s = document.getElementById("secondary_color");
        var pp = document.getElementById("primary_color_picker");
        var sp = document.getElementById("secondary_color_picker");
        var pv = radio.getAttribute("data-primary-color");
        var sv = radio.getAttribute("data-secondary-color");
        if (p && pv) { p.value = pv; if (pp) { pp.value = pv; } }
        if (s && sv) { s.value = sv; if (sp) { sp.value = sv; } }
      }
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        radio.dataset.userPicked = "1";
        applyEvent(radio);
      });
      if (radio.checked) { applyEvent(radio); }
    });

    form.querySelectorAll("[data-color-text], [data-color-picker], [data-palette]").forEach(function (el) {
      el.addEventListener("input", function () { form.dataset.colorTouched = "1"; });
      el.addEventListener("click", function () { form.dataset.colorTouched = "1"; });
    });

    initLocationField(form);
  }

  /* ------------------------------------------------------------------
     Location field: live feedback on what was pasted, and an Open Maps
     link that follows whatever the user has typed.
     ------------------------------------------------------------------ */
  var COORD_RE = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$/;
  var MAP_HOST_RE = /^https?:\/\/(maps\.app\.goo\.gl|goo\.gl\/maps|(www\.)?google\.[a-z.]{2,6}\/maps|maps\.google\.[a-z.]{2,6}|maps\.apple\.com)/i;

  function initLocationField(form) {
    var input = form.querySelector("[data-location-input]");
    var status = form.querySelector("[data-location-status]");
    var openBtn = form.querySelector("[data-open-maps]");
    if (!input) { return; }

    function check() {
      var value = input.value.trim();
      var venue = (form.querySelector("#venue_name") || {}).value || "";
      var address = (form.querySelector("#venue_address") || {}).value || "";

      if (openBtn) {
        // Send the user to the venue they've already typed, so they can
        // grab the pin without searching again.
        var query = value && COORD_RE.test(value)
          ? value
          : (venue + " " + address).trim();
        openBtn.href = query
          ? "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(query)
          : "https://www.google.com/maps";
      }

      if (!status) { return; }
      if (!value) {
        status.textContent = "";
        status.className = "location-status";
      } else if (COORD_RE.test(value)) {
        var parts = value.split(",");
        var lat = parseFloat(parts[0]), lng = parseFloat(parts[1]);
        if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
          status.textContent = "Coordinates recognised — guests can open this in their own map app.";
          status.className = "location-status is-ok";
        } else {
          status.textContent = "Those coordinates are out of range.";
          status.className = "location-status is-bad";
        }
      } else if (MAP_HOST_RE.test(value)) {
        status.textContent = "Map link recognised.";
        status.className = "location-status is-ok";
      } else {
        status.textContent = "Not a map link or coordinate pair — paste a Google/Apple Maps link, or 12.9716, 77.5946";
        status.className = "location-status is-bad";
      }
    }

    input.addEventListener("input", check);
    ["#venue_name", "#venue_address"].forEach(function (sel) {
      var el = form.querySelector(sel);
      if (el) { el.addEventListener("input", check); }
    });
    check();
  }

  /* ------------------------------------------------------------------
     Wire up
     ------------------------------------------------------------------ */
  document.addEventListener("DOMContentLoaded", function () {
    modal = document.getElementById("qrModal");
    initFilter();
    initSidebar();
    initAccordions();
    initRepeats();
    initDesignControls();
    initInviteForm();
    if (!modal) { return; }

    dialogTitle = modal.querySelector("[data-qr-dialog-title]");
    dialogKind = modal.querySelector("[data-qr-dialog-kind]");
    stageImg = modal.querySelector("[data-qr-stage-img]");
    linkBox = modal.querySelector("[data-qr-linkbox]");
    linkLabel = modal.querySelector("[data-qr-link-label]");
    linkValue = modal.querySelector("[data-qr-link-value]");
    btnDownload = modal.querySelector("[data-qr-action-download]");
    btnCopyImage = modal.querySelector("[data-qr-action-copy-image]");
    btnCopyLink = modal.querySelector("[data-qr-action-copy-link]");

    // Open the viewer — delegated, so cards added later still work.
    document.addEventListener("click", function (e) {
      var opener = e.target.closest(".qr-open");
      if (opener) {
        e.preventDefault();
        openModal({
          src: opener.getAttribute("data-qr-src"),
          download: opener.getAttribute("data-qr-download"),
          title: opener.getAttribute("data-qr-title"),
          kind: opener.getAttribute("data-qr-kind"),
          link: opener.getAttribute("data-qr-link"),
          linkLabel: opener.getAttribute("data-qr-link-label")
        });
        return;
      }

      // Inline copy buttons on the cards themselves
      var copyLinkBtn = e.target.closest("[data-copy-link]");
      if (copyLinkBtn) {
        e.preventDefault();
        copyText(copyLinkBtn.getAttribute("data-copy-link"));
        return;
      }
      var copyImgBtn = e.target.closest("[data-copy-image]");
      if (copyImgBtn) {
        e.preventDefault();
        copyImage(copyImgBtn.getAttribute("data-copy-image"));
      }
    });

    modal.querySelectorAll("[data-qr-close]").forEach(function (el) {
      el.addEventListener("click", closeModal);
    });
    modal.addEventListener("click", function (e) {
      if (e.target === modal) { closeModal(); }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains("open")) { closeModal(); }
      trapFocus(e);
    });

    btnCopyImage.addEventListener("click", function () { copyImage(current.src); });
    btnCopyLink.addEventListener("click", function () { copyText(current.link); });
  });
})();