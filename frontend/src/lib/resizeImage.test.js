import { targetSize, MAX_DIMENSION } from "./resizeImage";

describe("targetSize", () => {
  test("leaves images within the limit untouched", () => {
    expect(targetSize(800, 600)).toEqual({ width: 800, height: 600 });
    expect(targetSize(MAX_DIMENSION, 900)).toEqual({ width: MAX_DIMENSION, height: 900 });
  });

  test("scales landscape images so the long edge hits the limit", () => {
    expect(targetSize(4000, 3000)).toEqual({ width: 1280, height: 960 });
  });

  test("scales portrait images by their height", () => {
    expect(targetSize(3000, 4000)).toEqual({ width: 960, height: 1280 });
  });

  test("rounds to whole pixels and honours a custom limit", () => {
    expect(targetSize(1001, 333, 500)).toEqual({ width: 500, height: 166 });
  });
});
