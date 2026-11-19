import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

// A stylized bond network. The z coordinates let the layers respond to the pointer.
const atoms = [
  [-1.86, -.42, -.1], [-1.1, -.87, .06], [-.33, -.42, .16],
  [-.33, .48, -.05], [-1.1, .93, -.2], [-1.86, .48, -.16],
  [.49, -.7, .2], [1.05, -.03, .32], [.5, .7, .12],
  [-2.56, -.84, .12], [-1.1, 1.7, -.06], [1.84, -.08, .03],
  [.67, -1.48, -.18],
] as const;
const bonds = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [2, 6],
  [6, 7], [7, 8], [8, 3], [0, 9], [4, 10], [7, 11], [6, 12],
] as const;

export function ChemistryBackdrop({ scroller }: { scroller: RefObject<HTMLElement | null> }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvas.current;
    const scrollRoot = scroller.current;
    const ctx = element?.getContext('2d');
    if (!element || !scrollRoot || !ctx) return;

    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    const precisePointer = matchMedia('(pointer: fine)');
    const entranceStartedAt = performance.now();
    let frame = 0;
    let pointer: { x: number; y: number; showGlow: boolean } | null = null;
    let tiltX = 0;
    let tiltY = 0;

    function draw(time: number) {
      frame = 0;
      if (!element || !ctx || !scrollRoot) return;

      const { width, height } = element.getBoundingClientRect();
      const pixelRatio = Math.min(devicePixelRatio, 2);
      const pixelWidth = Math.round(width * pixelRatio);
      const pixelHeight = Math.round(height * pixelRatio);
      if (element.width !== pixelWidth || element.height !== pixelHeight) {
        element.width = pixelWidth;
        element.height = pixelHeight;
      }
      ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const still = reducedMotion.matches;
      const mobile = width < 720;
      const rtl = document.documentElement.dir === 'rtl';
      const activePointer = !still && pointer;
      const targetX = activePointer ? (activePointer.x / width - .5) * .32 : 0;
      const targetY = activePointer ? (activePointer.y / height - .5) * .3 : 0;
      tiltX = still ? 0 : tiltX + (targetX - tiltX) * .12;
      tiltY = still ? 0 : tiltY + (targetY - tiltY) * .12;

      const progress = still ? 1 : Math.min(1, Math.max(0, (time - entranceStartedAt) / 2300));
      const drift = (1 - progress) ** 3;
      const scroll = still ? 0 : scrollRoot.scrollTop;
      const scale = Math.min(width * (mobile ? .18 : .117), 152);
      const anchorX = width * (rtl ? (mobile ? .25 : .24) : (mobile ? .91 : .83));
      const anchorY = Math.min(height * .39, 320);
      const rotation = (rtl ? .18 : -.22) + tiltX * .4 - drift * .16;

      const projected = atoms.map(([x, y, z], index) => {
        const depth = z + x * (.15 + tiltX) - y * tiltY;
        const perspective = 1 + depth * .14;
        return {
          x: anchorX + (x * Math.cos(rotation) - y * Math.sin(rotation)) * scale * perspective + tiltX * 72,
          y: anchorY + (x * Math.sin(rotation) + y * Math.cos(rotation)) * scale * perspective - scroll * .19 + tiltY * 68 - drift * 22,
          depth,
          radius: scale * (index >= 9 ? .09 : .058) * perspective,
          terminal: index >= 9,
        };
      });

      ctx.globalAlpha = mobile ? .48 : .88;
      ctx.lineCap = 'round';
      for (const [start, end] of bonds) {
        const a = projected[start];
        const b = projected[end];
        const bond = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
        bond.addColorStop(0, a.terminal ? '#b2de8d' : '#439885');
        bond.addColorStop(1, b.terminal ? '#b2de8d' : '#439885');
        ctx.strokeStyle = bond;
        ctx.lineWidth = Math.max(1.8, scale * .035);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      for (const atom of projected.sort((a, b) => a.depth - b.depth)) {
        const { x, y, radius, terminal } = atom;
        const bead = ctx.createRadialGradient(x - radius * .3, y - radius * .4, 0, x, y, radius);
        bead.addColorStop(0, terminal ? '#f3ffd4' : '#c3f5e5');
        bead.addColorStop(.4, terminal ? '#bded90' : '#73cab7');
        bead.addColorStop(1, terminal ? '#54834e' : '#245750');
        ctx.fillStyle = bead;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      if (activePointer && activePointer.showGlow) {
        const glow = ctx.createRadialGradient(activePointer.x, activePointer.y, 3, activePointer.x, activePointer.y, 82);
        glow.addColorStop(0, '#92ead422');
        glow.addColorStop(1, '#92ead400');
        ctx.globalAlpha = 1;
        ctx.fillStyle = glow;
        ctx.fillRect(activePointer.x - 82, activePointer.y - 82, 164, 164);

        ctx.strokeStyle = '#a6e8cf66';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(activePointer.x + 3, activePointer.y + 3, 11, 0, Math.PI * 2);
        ctx.stroke();
      }

      if (!still && (progress < 1 || Math.abs(targetX - tiltX) + Math.abs(targetY - tiltY) > .001)) schedule();
    }

    function schedule() {
      if (!frame) frame = requestAnimationFrame(draw);
    }

    function track(event: PointerEvent) {
      if (!precisePointer.matches || reducedMotion.matches || event.pointerType !== 'mouse') return;
      pointer = {
        x: event.clientX,
        y: event.clientY,
        showGlow: event.target instanceof Element && !event.target.closest('.panel, a, button, textarea'),
      };
      schedule();
    }

    function clearPointer() {
      pointer = null;
      schedule();
    }

    const direction = new MutationObserver(schedule);
    direction.observe(document.documentElement, { attributes: true, attributeFilter: ['dir'] });
    window.addEventListener('resize', schedule);
    scrollRoot.addEventListener('scroll', schedule, { passive: true });
    scrollRoot.addEventListener('pointermove', track, { passive: true });
    scrollRoot.addEventListener('pointerleave', clearPointer);
    reducedMotion.addEventListener('change', clearPointer);
    precisePointer.addEventListener('change', clearPointer);
    schedule();

    return () => {
      cancelAnimationFrame(frame);
      direction.disconnect();
      window.removeEventListener('resize', schedule);
      scrollRoot.removeEventListener('scroll', schedule);
      scrollRoot.removeEventListener('pointermove', track);
      scrollRoot.removeEventListener('pointerleave', clearPointer);
      reducedMotion.removeEventListener('change', clearPointer);
      precisePointer.removeEventListener('change', clearPointer);
    };
  }, [scroller]);

  return (
    <div className="chemistry-backdrop" aria-hidden="true">
      <div className="chemistry-grid" />
      <div className="chemistry-orbits"><i /><i /><i /></div>
      <canvas ref={canvas} />
    </div>
  );
}
