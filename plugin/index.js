// The OpenCode entry of breadcrumbs: the server part of the plugin (see setup.js for what it registers). OpenCode loads
// it from the root of this folder (package.json: exports ".").
import { Plugin, Skill } from "@opencode/plugin";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { setup } from "./setup.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default Plugin.define({
  id: "breadcrumbs",
  async setup(ctx) {
    return setup(ctx, {
      root,
      brand: {
        skillID: Skill.ID.make,
        skillName: Skill.Name.make,
        skillPath: Skill.Info.fields.path.make,
      },
    });
  },
});
