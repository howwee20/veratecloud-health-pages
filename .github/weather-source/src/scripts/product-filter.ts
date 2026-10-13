// Text filter for the product directories (Current Weather, Forecast Products).
// Progressive enhancement: the server-rendered page lists every product, and
// this script only hides the ones that do not match what was typed.

const input = document.querySelector<HTMLInputElement>('#product-search');
const count = document.querySelector<HTMLElement>('#product-count');

if (input && count) {
  const products = Array.from(document.querySelectorAll<HTMLElement>('[data-product]'));
  const groups = Array.from(document.querySelectorAll<HTMLElement>('[data-product-group]'));
  const sections = Array.from(document.querySelectorAll<HTMLElement>('[data-product-section]'));
  const clear = document.querySelector<HTMLButtonElement>('#product-clear');
  const empty = document.querySelector<HTMLElement>('#product-empty');
  const total = products.length;

  const shownIn = (el: HTMLElement) => el.querySelectorAll('[data-product]:not([hidden])').length;

  const apply = (): void => {
    const terms = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const product of products) {
      const text = product.dataset.text ?? '';
      const match = terms.every((term) => text.includes(term));
      product.hidden = !match;
      if (match) shown += 1;
    }
    for (const group of groups) group.hidden = shownIn(group) === 0;
    for (const section of sections) {
      const n = shownIn(section);
      section.hidden = n === 0;
      const label = section.querySelector<HTMLElement>('[data-section-count]');
      if (label) {
        const all = Number(label.dataset.total ?? n);
        label.textContent = n === all ? `${all} ${all === 1 ? 'product' : 'products'}` : `${n} of ${all} shown`;
      }
    }
    count.textContent = `Showing ${shown} of ${total} products`;
    if (clear) clear.hidden = terms.length === 0;
    if (empty) empty.hidden = shown !== 0;
  };

  const reset = (): void => {
    input.value = '';
    apply();
  };

  input.addEventListener('input', apply);
  // Escape clears a search field in some browsers but not all; make it consistent.
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && input.value !== '') {
      event.preventDefault();
      reset();
    }
  });
  clear?.addEventListener('click', () => {
    reset();
    input.focus();
  });
  // A link to a section the filter has hidden clears the filter rather than going nowhere.
  window.addEventListener('hashchange', () => {
    const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
    if (target?.closest('[hidden]')) {
      reset();
      target.scrollIntoView();
    }
  });
  // The browser may restore a typed value when returning to the page.
  window.addEventListener('pageshow', apply);
  apply();
}
