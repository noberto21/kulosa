(function () {
  "use strict";

  // Mobile menu
  var toggle = document.querySelector("[data-menu-toggle]");
  var menu = document.querySelector("[data-menu]");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("hidden") === false;
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "Close" : "Menu";
    });
  }

  // Copy event link
  var copyBtn = document.querySelector("[data-copy-link]");
  var status = document.querySelector("[data-copy-status]");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var url = copyBtn.getAttribute("data-copy-link");
      function done(msg) { if (status) status.textContent = msg; }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(function () { done("Link copied."); }, function () { done("Couldn't copy. Copy it from the address bar."); });
      } else {
        var ta = document.createElement("textarea");
        ta.value = url; ta.setAttribute("readonly", ""); ta.style.position = "absolute"; ta.style.left = "-9999px";
        document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done("Link copied."); } catch (e) { done("Couldn't copy. Copy it from the address bar."); }
        document.body.removeChild(ta);
      }
    });
  }

  // Event form: hide fields that don't apply. The server validates everything regardless.
  var form = document.querySelector("[data-event-form]");
  if (form) {
    var free = form.querySelector("#id_is_free");
    var price = form.querySelector("[data-price-field]");
    var type = form.querySelector("#id_event_type");
    var place = form.querySelector("[data-place-fields]");
    function sync() {
      if (free && price) price.hidden = free.checked;
      if (type && place) place.hidden = type.value === "ONLINE";
    }
    [free, type].forEach(function (el) { if (el) el.addEventListener("change", sync); });
    sync();
  }
})();
