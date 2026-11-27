import type { CSSVariablesResolver, MantineColorsTuple } from "@mantine/core";
import { createTheme } from "@mantine/core";

/**
 * MasTec blue as a Mantine color.
 *
 * Mantine needs 10 shades per color, but the brand has one blue. Shade 6 (the primary
 * shade below) is mastec-blue; shades 7 to 9 are dark-navy, which the design system
 * uses for the hover and pressed state of mastec-blue buttons.
 */
const mastecBlue: MantineColorsTuple = [
  "#0057b8",
  "#0057b8",
  "#0057b8",
  "#0057b8",
  "#0057b8",
  "#0057b8",
  "#0057b8",
  "#072037",
  "#072037",
  "#072037",
];

/**
 * Mantine theme for Atlas, using the Project Atlas design system.
 *
 * Fonts point at the CSS variables in src/styles/global.css so there is one place to
 * change them. Colors are hex because Mantine works out lighter variants from them.
 */
export const theme = createTheme({
  primaryColor: "mastecBlue",
  primaryShade: 6,
  colors: { mastecBlue },
  black: "#072037",
  white: "#ffffff",
  fontFamily: "var(--font-ui)",
  fontFamilyMonospace: "var(--font-mono)",
  fontSizes: {
    xs: "12px",
    sm: "12px",
    md: "14px",
    lg: "15px",
    xl: "18px",
  },
  lineHeights: {
    xs: "16px",
    sm: "16px",
    md: "20px",
    lg: "20px",
    xl: "24px",
  },
  headings: {
    fontFamily: "var(--font-ui)",
    fontWeight: "700",
    sizes: {
      h1: { fontSize: "32px", lineHeight: "40px" },
      h2: { fontSize: "24px", lineHeight: "32px" },
      h3: { fontSize: "18px", lineHeight: "24px" },
    },
  },
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
  },
  radius: {
    xs: "2px",
    sm: "2px",
    md: "4px",
    lg: "4px",
    xl: "4px",
  },
  defaultRadius: "sm",
});

/**
 * Sets the page background to lt-gray; Mantine's default is white.
 */
export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: { "--mantine-color-body": "#eaeaea" },
  dark: {},
});
