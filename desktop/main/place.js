// Window placement, kept free of Electron so it can be tested.

// Bounds for a w x h card whose bottom-right corner is at `anchor` = [right, bottom], pulled wholly inside
// the work area of the display nearest the card's center, so a removed or rearranged monitor can't strand
// it off-screen. `workAreas` is a list of { x, y, width, height }.
function fitInside(anchor, w, h, workAreas) {
  const [r, b] = anchor;
  const cx = r - w / 2, cy = b - h / 2;
  const dist = (a) => {
    const dx = Math.max(a.x - cx, 0, cx - (a.x + a.width));
    const dy = Math.max(a.y - cy, 0, cy - (a.y + a.height));
    return dx * dx + dy * dy;
  };
  const wa = workAreas.reduce((best, a) => (dist(a) < dist(best) ? a : best));
  const x = Math.min(Math.max(Math.round(r - w), wa.x), wa.x + Math.max(0, wa.width - w));
  const y = Math.min(Math.max(Math.round(b - h), wa.y), wa.y + Math.max(0, wa.height - h));
  return { x, y, width: w, height: h };
}

module.exports = { fitInside };
