/* =====================================================================
   invitation.js — public invitation card behaviour.

   Two jobs:
     1. Make "Add to calendar" as close to unmissable as a web page can
        get, without hijacking the browser. We surface a nudge bar shortly
        after the page settles, and remember (per invitation) once the
        guest has acted on it.
     2. Prefer the phone's own map app over the browser when we have
        coordinates — a geo: link lets Android offer Maps, Waze, or
        whatever the guest actually uses.
   ===================================================================== */
(function () {
  "use strict";

  var STORE_PREFIX = "vegroww.invite.saved.";

  function pageKey() {
    return STORE_PREFIX + window.location.pathname;
  }

  function markSaved() {
    try { localStorage.setItem(pageKey(), "1"); } catch (e) { /* private mode */ }
  }

  function alreadySaved() {
    try { return localStorage.getItem(pageKey()) === "1"; } catch (e) { return false; }
  }

  /* ------------------------------------------------------------------
     Maps: use geo: on Android where a native app is likely registered.
     iOS has no geo: handler, and desktop has none either, so both keep
     the https Google Maps URL that's already in the href.
     ------------------------------------------------------------------ */
  function isAndroid() {
    return /android/i.test(navigator.userAgent);
  }

  function initMapLinks() {
    if (!isAndroid()) { return; }
    document.querySelectorAll("[data-geo-uri]").forEach(function (link) {
      var geo = link.getAttribute("data-geo-uri");
      if (!geo) { return; }
      link.addEventListener("click", function (e) {
        // Try the native handler; if nothing takes it the browser stays
        // put and we fall back to the original https link.
        var fallback = link.getAttribute("href");
        e.preventDefault();
        var timer = setTimeout(function () { window.location.href = fallback; }, 700);
        window.addEventListener("blur", function once() {
          clearTimeout(timer);
          window.removeEventListener("blur", once);
        });
        window.location.href = geo;
      });
    });
  }

  /* ------------------------------------------------------------------
     Calendar nudge
     ------------------------------------------------------------------ */
  function initCalendar() {
    var nudge = document.querySelector("[data-calendar-nudge]");

    document.querySelectorAll("[data-add-calendar]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        markSaved();
        if (nudge) { nudge.hidden = true; }
      });
    });

    if (!nudge || alreadySaved()) { return; }

    // Let the guest read the card first — an instant popup reads as spam.
    setTimeout(function () {
      if (!alreadySaved()) {
        nudge.hidden = false;
        nudge.classList.add("is-in");
      }
    }, 2600);

    var dismiss = nudge.querySelector("[data-nudge-dismiss]");
    if (dismiss) {
      dismiss.addEventListener("click", function () {
        nudge.hidden = true;
        markSaved();   // don't badger someone who has said no
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initMapLinks();
    initCalendar();
  });
})();
