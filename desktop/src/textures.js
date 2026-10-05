// Small procedural textures, drawn once with canvas 2D and shared by every scene.
import { Texture } from "pixi.js";

function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d"), w, h);
  return Texture.from(c);
}

let cache = null;

export function textures() {
  if (cache) return cache;
  cache = {
    // a leaf: white so it takes any tint, lit along its top edge, with a faint midrib
    leaf: canvasTexture(48, 26, (x, w, h) => {
      x.translate(w / 2, h / 2);
      x.beginPath();
      x.moveTo(-w / 2 + 1, 0);
      x.bezierCurveTo(-w / 4, -h / 2 + 1, w / 4, -h / 2 + 1, w / 2 - 1, 0);
      x.bezierCurveTo(w / 4, h / 2 - 1, -w / 4, h / 2 - 1, -w / 2 + 1, 0);
      const g = x.createLinearGradient(0, -h / 2, 0, h / 2);
      g.addColorStop(0, "#ffffff");
      g.addColorStop(0.55, "#e6e6e6");
      g.addColorStop(1, "#bdbdbd");
      x.fillStyle = g;
      x.fill();
      x.strokeStyle = "rgba(0,0,0,0.16)";
      x.lineWidth = 1.2;
      x.beginPath();
      x.moveTo(-w / 2 + 5, 0.5);
      x.quadraticCurveTo(0, -1.5, w / 2 - 5, 0.5);
      x.stroke();
    }),
    // a solid disc with a soft rim, for canopy domes, drops and buds
    disc: canvasTexture(64, 64, (x, w) => {
      const g = x.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.82, "rgba(255,255,255,1)");
      g.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = g;
      x.fillRect(0, 0, w, w);
    }),
    // a soft glow, for light, motes and fireflies (use with additive blending)
    glow: canvasTexture(128, 128, (x, w) => {
      const g = x.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.25, "rgba(255,255,255,0.55)");
      g.addColorStop(0.6, "rgba(255,255,255,0.12)");
      g.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = g;
      x.fillRect(0, 0, w, w);
    }),
    // a ripple ring
    ring: canvasTexture(64, 64, (x, w) => {
      x.strokeStyle = "white";
      x.lineWidth = 3;
      x.beginPath();
      x.arc(w / 2, w / 2, w / 2 - 3, 0, Math.PI * 2);
      x.stroke();
    }),
    // a light shaft: bright along its center line, fading to the sides and the far end
    shaft: canvasTexture(64, 256, (x, w, h) => {
      const g = x.createLinearGradient(0, 0, w, 0);
      g.addColorStop(0, "rgba(255,255,255,0)");
      g.addColorStop(0.5, "rgba(255,255,255,1)");
      g.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = g;
      x.fillRect(0, 0, w, h);
      x.globalCompositeOperation = "destination-in";
      const f = x.createLinearGradient(0, 0, 0, h);
      f.addColorStop(0, "rgba(0,0,0,1)");
      f.addColorStop(1, "rgba(0,0,0,0)");
      x.fillStyle = f;
      x.fillRect(0, 0, w, h);
    }),
  };
  return cache;
}
