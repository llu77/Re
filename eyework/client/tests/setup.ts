/*
 * jsdom لا يعرف <dialog>.showModal ولا close: بديلٌ يضع السمة open ويرفعها، يكفي لاختبار
 * ما تفعله المكوّنات حولهما (التركيز، Escape، الإغلاق). السلوك الحقيقي يُختبر في Chromium.
 */

if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "")
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open")
  }
}
