(function () {
  "use strict";

  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-site-nav]");

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.getAttribute("data-open") === "true";
      nav.setAttribute("data-open", String(!open));
      toggle.setAttribute("aria-expanded", String(!open));
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        nav.setAttribute("data-open", "false");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.querySelectorAll("[data-year]").forEach(function (node) {
    node.textContent = String(new Date().getFullYear());
  });

  var form = document.querySelector("[data-contact-form]");
  if (!form) return;

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var status = form.querySelector("[data-form-status]");
    if (!form.reportValidity()) return;

    var data = new FormData(form);
    var lines = [
      "Name: " + String(data.get("name") || ""),
      "Email: " + String(data.get("email") || ""),
      "Company: " + String(data.get("company") || "Not provided"),
      "Target market: " + String(data.get("market") || "Not specified"),
      "Service: " + String(data.get("service") || "Not specified"),
      "",
      "Project summary:",
      String(data.get("message") || "")
    ];
    var subject = "Documentation readiness enquiry - " + String(data.get("company") || data.get("name") || "website");
    var href = "mailto:service@unicertgroup.com?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(lines.join("\n"));
    if (status) status.textContent = "Your email application should now open. This website has not transmitted or stored your form data.";
    window.location.href = href;
  });
})();
