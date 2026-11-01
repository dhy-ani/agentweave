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

  test("closet photos keep full URLs and resolve API-relative paths", () => {
    delete process.env.REACT_APP_API_URL;
    const { closetImageUrl } = require("./config");
    expect(closetImageUrl("https://x.public.blob.vercel-storage.com/closet/u1/a.jpg")).toBe("https://x.public.blob.vercel-storage.com/closet/u1/a.jpg");
    expect(closetImageUrl("http://cdn.test/a.jpg")).toBe("http://cdn.test/a.jpg");
    expect(closetImageUrl("/closet-images/u1/a.jpg")).toBe("http://localhost:8001/closet-images/u1/a.jpg");
  });
});
