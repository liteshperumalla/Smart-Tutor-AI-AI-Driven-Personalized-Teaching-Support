import { getSafeNextPath, loginPathFor } from "../safe-next";

describe("safe next paths", () => {
  it("keeps an internal destination", () => {
    expect(getSafeNextPath("/quiz?course=info-5731")).toBe("/quiz?course=info-5731");
    expect(loginPathFor("/chat?course=info-5731")).toBe("/login?next=%2Fchat%3Fcourse%3Dinfo-5731");
  });

  it("rejects external and protocol-relative destinations", () => {
    expect(getSafeNextPath("https://malicious.example")).toBe("/");
    expect(getSafeNextPath("//malicious.example")).toBe("/");
  });
});
