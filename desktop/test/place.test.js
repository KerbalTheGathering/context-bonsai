const test = require("node:test");
const assert = require("node:assert/strict");
const { fitInside } = require("../main/place.js");

const primary = { x: 0, y: 0, width: 1920, height: 1040 };
const left = { x: -2560, y: 0, width: 2560, height: 1400 };

test("an on-screen anchor is used as is", () => {
  assert.deepEqual(fitInside([1896, 1016], 300, 400, [primary]), { x: 1596, y: 616, width: 300, height: 400 });
});

test("a card from a removed monitor comes back onto the nearest one", () => {
  const b = fitInside([-1000, 900], 300, 400, [primary]); // was on the left monitor, now unplugged
  assert.equal(b.x, 0);
  assert.equal(b.y, 500);
});

test("a card hanging off an edge is pulled fully inside", () => {
  assert.deepEqual(fitInside([2000, 1200], 300, 400, [primary]), { x: 1620, y: 640, width: 300, height: 400 });
  assert.deepEqual(fitInside([100, 100], 300, 400, [primary]), { x: 0, y: 0, width: 300, height: 400 });
});

test("the nearest of several monitors wins", () => {
  const b = fitInside([-100, 700], 300, 400, [primary, left]);
  assert.equal(b.x, -400);
  assert.equal(b.y, 300);
});

test("a card bigger than the work area sits at its top-left", () => {
  assert.deepEqual(fitInside([500, 500], 3000, 2000, [primary]), { x: 0, y: 0, width: 3000, height: 2000 });
});
