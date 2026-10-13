// Generic, attribute-driven list filtering. Progressive enhancement: without
// this script every row is visible and the controls are simply inert.
//
//   [data-filter-scope]            wrapper around controls + rows
//   [data-filter-row]              a row; reads data-text and other data-* values
//   [data-filter-text]             search box, all words must appear in data-text
//   [data-filter-attr="name"]      <select>; row.dataset[name] must equal its value ("all" = any)
//   [data-filter-flag="name"]      checkbox; when checked, row.dataset[name] must be in data-flag-values
//   [data-filter-min|max="name"]   <select>; inclusive string range on row.dataset[name]
//   [data-filter-count]            status text, data-template="Showing {n} of {total} things"
//   [data-filter-empty]            shown when nothing matches
//   [data-filter-reset]            button that restores every control
function setup(scope: HTMLElement): void {
  const rows = Array.from(scope.querySelectorAll<HTMLElement>('[data-filter-row]'));
  const texts = Array.from(scope.querySelectorAll<HTMLInputElement>('[data-filter-text]'));
  const attrs = Array.from(scope.querySelectorAll<HTMLSelectElement>('[data-filter-attr]'));
  const flags = Array.from(scope.querySelectorAll<HTMLInputElement>('[data-filter-flag]'));
  const mins = Array.from(scope.querySelectorAll<HTMLSelectElement>('[data-filter-min]'));
  const maxs = Array.from(scope.querySelectorAll<HTMLSelectElement>('[data-filter-max]'));
  const count = scope.querySelector<HTMLElement>('[data-filter-count]');
  const empty = scope.querySelector<HTMLElement>('[data-filter-empty]');
  const groups = Array.from(scope.querySelectorAll<HTMLElement>('[data-filter-group]'));

  const apply = () => {
    const words = texts.flatMap((input) => input.value.toLowerCase().split(/\s+/).filter(Boolean));
    let shown = 0;
    for (const row of rows) {
      const data = row.dataset;
      const ok =
        words.every((w) => (data.text ?? '').includes(w)) &&
        attrs.every((s) => s.value === 'all' || data[s.dataset.filterAttr!] === s.value) &&
        flags.every((f) => !f.checked || (f.dataset.flagValues ?? '').split(',').includes(data[f.dataset.filterFlag!] ?? '')) &&
        mins.every((s) => (data[s.dataset.filterMin!] ?? '') >= s.value) &&
        maxs.every((s) => (data[s.dataset.filterMax!] ?? '') <= s.value);
      row.hidden = !ok;
      if (ok) shown += 1;
    }
    for (const group of groups) {
      group.hidden = !group.querySelector('[data-filter-row]:not([hidden])');
    }
    if (count) count.textContent = (count.dataset.template ?? '{n} of {total}').replace('{n}', String(shown)).replace('{total}', String(rows.length));
    if (empty) empty.hidden = shown !== 0;
  };

  for (const control of [...texts, ...attrs, ...flags, ...mins, ...maxs]) {
    control.addEventListener('input', apply);
    control.addEventListener('change', apply);
  }
  scope.querySelector<HTMLButtonElement>('[data-filter-reset]')?.addEventListener('click', () => {
    texts.forEach((input) => (input.value = ''));
    flags.forEach((input) => (input.checked = false));
    attrs.forEach((select) => (select.value = 'all'));
    mins.forEach((select) => (select.selectedIndex = 0));
    maxs.forEach((select) => (select.selectedIndex = select.options.length - 1));
    apply();
  });
  apply();
}

document.querySelectorAll<HTMLElement>('[data-filter-scope]').forEach(setup);
