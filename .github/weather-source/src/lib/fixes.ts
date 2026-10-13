// Defects found by testing during the build of this prototype, and what was
// done about them. Only real, observed defects are listed.
export const fixes: { found: string; how: string; fix: string }[] = [
  {
    found: 'Station and report pages scrolled sideways at 320 px (page width 1,250 px).',
    how: 'Scripted reflow check at 320 px, then inspection of overflowing elements.',
    fix: 'Screen-reader-only text inside scrolling tables was escaping its container; table regions now contain it. Grid children may shrink below their content width. Long status badges wrap.',
  },
  {
    found: 'Chart end labels were cut off and the axis unit collided with the top tick label.',
    how: 'Visual review of screenshots at 1280 px.',
    fix: 'Chart minimum width reduced and top margin increased; unit label moved above the plot.',
  },
  {
    found: 'Host names on the Legacy Rescue Map root boxes failed colour contrast (grey text on dark green).',
    how: 'axe-core rule color-contrast, 4 elements at both widths.',
    fix: 'Text colour on dark boxes changed to a light tint.',
  },
  {
    found: 'Scrollable text excerpts carried an aria-label on an element with no role.',
    how: 'axe-core flagged aria-prohibited-attr for review on three comparison pages.',
    fix: 'Excerpts are now wrapped in a labelled, focusable region.',
  },
];
