// Generated from the Google Fonts CSS for these families
// (fonts.googleapis.com/css2, variable weight axes). Files are in
// public/fonts/google with their OFL licenses.
//
// next/font/local loads the latin file of each family; this module adds the
// other subsets as extra @font-face rules under the same family name. Each
// rule carries Google's unicode-range, so a browser only downloads a subset
// file when the page uses one of its characters, as with next/font/google.

type Subset = { file: string; unicodeRange: string };

const EXTRA_SUBSETS: Record<string, { weight: string; subsets: Subset[] }> = {
  "Geist Mono": {
    weight: "100 900",
    subsets: [
      { file: "GeistMono-Variable-cyrillic-ext.woff2", unicodeRange: "U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F" },
      { file: "GeistMono-Variable-cyrillic.woff2", unicodeRange: "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116" },
      { file: "GeistMono-Variable-symbols2.woff2", unicodeRange: "U+2000-2001, U+2004-2008, U+200A, U+23B8-23BD, U+2500-259F" },
      { file: "GeistMono-Variable-vietnamese.woff2", unicodeRange: "U+0102-0103, U+0110-0111, U+0128-0129, U+0168-0169, U+01A0-01A1, U+01AF-01B0, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+1EA0-1EF9, U+20AB" },
      { file: "GeistMono-Variable-latin-ext.woff2", unicodeRange: "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF" },
    ],
  },
  "Inter": {
    weight: "100 900",
    subsets: [
      { file: "Inter-Variable-cyrillic-ext.woff2", unicodeRange: "U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F" },
      { file: "Inter-Variable-cyrillic.woff2", unicodeRange: "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116" },
      { file: "Inter-Variable-greek-ext.woff2", unicodeRange: "U+1F00-1FFF" },
      { file: "Inter-Variable-greek.woff2", unicodeRange: "U+0370-0377, U+037A-037F, U+0384-038A, U+038C, U+038E-03A1, U+03A3-03FF" },
      { file: "Inter-Variable-vietnamese.woff2", unicodeRange: "U+0102-0103, U+0110-0111, U+0128-0129, U+0168-0169, U+01A0-01A1, U+01AF-01B0, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+1EA0-1EF9, U+20AB" },
      { file: "Inter-Variable-latin-ext.woff2", unicodeRange: "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF" },
    ],
  },
  "Space Grotesk": {
    weight: "300 700",
    subsets: [
      { file: "SpaceGrotesk-Variable-vietnamese.woff2", unicodeRange: "U+0102-0103, U+0110-0111, U+0128-0129, U+0168-0169, U+01A0-01A1, U+01AF-01B0, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+1EA0-1EF9, U+20AB" },
      { file: "SpaceGrotesk-Variable-latin-ext.woff2", unicodeRange: "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF" },
    ],
  },
};

/** @font-face rules for a family's non-latin subsets, under `fontFamily`
 * (the family name next/font generated for its latin face). */
export function extraSubsetFontFaces(family: string, fontFamily: string): string {
  const { weight, subsets } = EXTRA_SUBSETS[family];
  const name = fontFamily.split(",")[0].trim();
  return subsets
    .map(
      ({ file, unicodeRange }) =>
        `@font-face{font-family:${name};src:url(/fonts/google/${file}) format("woff2");` +
        `font-weight:${weight};font-style:normal;font-display:swap;unicode-range:${unicodeRange}}`
    )
    .join("");
}
