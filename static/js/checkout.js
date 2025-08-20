// Checkout interactions (no template logic inside)
(() => {
  const $ = (sel) => document.querySelector(sel);
  const on = (el, ev, fn) => el && el.addEventListener(ev, fn, { passive: true });

  function toggleInvoiceFields() {
    const want = $("#id_want_invoice");
    const box = document.getElementById("invoice-fields");
    if (!want || !box) return;
    box.hidden = !want.checked;
    if (want.checked) toggleTcknVkn();
  }

  function toggleTcknVkn() {
    const type = $("#id_invoice_type");
    const tcknRow = document.getElementById("row-tckn");
    const vknRow = document.getElementById("row-vkn");
    const taxRow = document.getElementById("row-tax-office");
    if (!type) return;
    const isCorp = String(type.value).toLowerCase() === "kurumsal";
    if (tcknRow) tcknRow.hidden = isCorp;
    if (vknRow) vknRow.hidden = !isCorp;
    if (taxRow) taxRow.hidden = !isCorp;
  }

  function init() {
    toggleInvoiceFields();
    on($("#id_want_invoice"), "change", toggleInvoiceFields);
    on($("#id_invoice_type"), "change", toggleTcknVkn);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();