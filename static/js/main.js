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
    var originalText = copyBtn.textContent;
    copyBtn.addEventListener("click", function () {
      var url = copyBtn.getAttribute("data-copy-link");
      function done(msg, success) {
        if (status) status.textContent = msg;
        if (success) {
          copyBtn.textContent = "✓ Copied!";
          copyBtn.classList.add("bg-emerald-600");
          setTimeout(function () {
            copyBtn.textContent = originalText;
            copyBtn.classList.remove("bg-emerald-600");
          }, 2000);
        }
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(
          function () { done("Link copied.", true); },
          function () { done("Couldn't copy. Copy it from the address bar.", false); }
        );
      } else {
        var ta = document.createElement("textarea");
        ta.value = url; ta.setAttribute("readonly", ""); ta.style.position = "absolute"; ta.style.left = "-9999px";
        document.body.appendChild(ta); ta.select();
        try {
          document.execCommand("copy");
          done("Link copied.", true);
        } catch (e) {
          done("Couldn't copy. Copy it from the address bar.", false);
        }
        document.body.removeChild(ta);
      }
    });
  }

  // Live image poster preview
  var coverInput = document.querySelector("#id_cover_image");
  var previewContainer = document.querySelector("[data-poster-preview]");
  var previewImg = previewContainer ? previewContainer.querySelector("img") : null;
  if (coverInput && previewContainer && previewImg) {
    coverInput.addEventListener("change", function () {
      var file = coverInput.files && coverInput.files[0];
      if (file && file.type && file.type.startsWith("image/")) {
        previewImg.src = URL.createObjectURL(file);
        previewContainer.classList.remove("hidden");
      } else {
        previewContainer.classList.add("hidden");
        previewImg.src = "";
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
