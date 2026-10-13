import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readFile } from "node:fs/promises";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const canonical = await readFile(resolve(root, "app/webui/static/design-tokens.css"), "utf8");
await writeFile(resolve(root, "desktop-ui/src/app/design-tokens.css"), canonical, "utf8");
