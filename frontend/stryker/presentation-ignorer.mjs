import { PluginKind, declareValuePlugin } from "@stryker-mutator/api/plugin";

// Mutating Tailwind class strings or inline animation style objects only
// changes how something looks, which unit tests deliberately do not pin down
// (that belongs to visual review). Ignoring them keeps the mutation score a
// measure of behaviour rather than of styling.
const PRESENTATION_ATTRIBUTES = new Set(["className", "style"]);

export const strykerPlugins = [
  declareValuePlugin(PluginKind.Ignore, "presentation", {
    shouldIgnore(path) {
      const attr = path.findParent(p => p.isJSXAttribute());
      if (attr && PRESENTATION_ATTRIBUTES.has(attr.node.name.name)) {
        return "Presentation-only JSX attribute (className/style); covered by visual review, not unit tests.";
      }
      return undefined;
    },
  }),
];
