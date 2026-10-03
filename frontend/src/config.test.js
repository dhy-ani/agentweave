describe("config", () => {
  const original = process.env.REACT_APP_API_URL;

  afterEach(() => {
    process.env.REACT_APP_API_URL = original;
    jest.resetModules();
  });

  test("defaults to the local backend", () => {
    delete process.env.REACT_APP_API_URL;
    const { API } = require("./config");
    expect(API).toBe("http://localhost:8001");
  });

  test("uses the configured URL without trailing slashes", () => {
    process.env.REACT_APP_API_URL = "https://agentweave-api.vercel.app//";
    const { API, imageUrl } = require("./config");
    expect(API).toBe("https://agentweave-api.vercel.app");
    expect(imageUrl("boho beach_1.jpg")).toBe("https://agentweave-api.vercel.app/images/boho%20beach_1.jpg");
  });

  test("prefers a stored blob URL for wardrobe images", () => {
    delete process.env.REACT_APP_API_URL;
    const { wardrobeImageUrl } = require("./config");
    expect(wardrobeImageUrl({ image_url: "https://blob.example/x.jpg", filename: "x.jpg" })).toBe("https://blob.example/x.jpg");
    expect(wardrobeImageUrl({ filename: "x.jpg" })).toBe("http://localhost:8001/wardrobe-images/x.jpg");
  });
});
