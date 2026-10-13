// Pointer tooltip for build-time SVG charts. A convenience only: every value
// shown here is also in the page's data table.
interface Payload { unit: string; x: number[]; slots: string[]; series: { label: string; raw: string[] }[]; width: number }

function init(figure: HTMLElement): void {
  const data = JSON.parse(figure.dataset.chart ?? 'null') as Payload | null;
  const svg = figure.querySelector<SVGSVGElement>('svg.chart');
  const hit = figure.querySelector<SVGRectElement>('.hit');
  const cross = figure.querySelector<SVGLineElement>('.crosshair');
  const scroller = figure.querySelector<HTMLElement>('.chart-scroll');
  if (!data || !svg || !hit || !cross || !scroller) return;

  const tip = document.createElement('div');
  tip.className = 'chart-tip';
  tip.hidden = true;
  tip.setAttribute('aria-hidden', 'true');
  scroller.append(tip);

  const hide = () => {
    tip.hidden = true;
    cross.style.visibility = 'hidden';
  };

  hit.addEventListener('pointermove', (event) => {
    const box = svg.getBoundingClientRect();
    const scale = data.width / box.width;
    const px = (event.clientX - box.left) * scale;
    let nearest = 0;
    for (let i = 1; i < data.x.length; i += 1) {
      if (Math.abs(data.x[i] - px) < Math.abs(data.x[nearest] - px)) nearest = i;
    }
    cross.setAttribute('x1', String(data.x[nearest]));
    cross.setAttribute('x2', String(data.x[nearest]));
    cross.style.visibility = 'visible';

    tip.replaceChildren();
    const head = document.createElement('b');
    head.textContent = data.slots[nearest];
    tip.append(head);
    for (const series of data.series) {
      const raw = series.raw[nearest];
      const numeric = raw !== '' && !Number.isNaN(Number(raw));
      const line = document.createElement('div');
      line.textContent = `${series.label}: ${numeric ? `${raw} ${data.unit}` : `${raw} (no value reported)`}`;
      tip.append(line);
    }
    tip.hidden = false;
    const left = data.x[nearest] / scale + scroller.scrollLeft;
    const flip = left + tip.offsetWidth + 16 > scroller.scrollWidth;
    tip.style.left = `${flip ? left - tip.offsetWidth - 10 : left + 10}px`;
    tip.style.top = '8px';
  });
  hit.addEventListener('pointerleave', hide);
  scroller.addEventListener('scroll', hide, { passive: true });
}

document.querySelectorAll<HTMLElement>('figure[data-chart]').forEach(init);
