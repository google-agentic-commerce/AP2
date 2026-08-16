// Generates Zod schemas + TypeScript types from the canonical AP2 JSON
// Schemas in code/sdk/schemas/ap2/. Mirrors the role of
// code/sdk/schemas/generate.py on the Python side, so the TS SDK can't drift
// from the protocol's source of truth. Run via `npm run generate`.

import {
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import $RefParser from "@apidevtools/json-schema-ref-parser";
import { jsonSchemaToZod } from "json-schema-to-zod";
import prettier from "prettier";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCHEMAS_DIR = path.resolve(__dirname, "../../schemas/ap2");
const TYPES_DIR = path.join(SCHEMAS_DIR, "types");
const OUT_TYPES_DIR = path.resolve(__dirname, "../src/generated/types");
const OUT_MANDATES_DIR = path.resolve(__dirname, "../src/generated/mandates");

// Each schema declares an absolute $id (e.g. https://ap2-protocol.org/schemas/...),
// which JSON Schema treats as the base URI for resolving its own relative $refs.
// That sends "types/merchant.json" out to the network instead of the sibling
// file on disk. We mirror the schema tree into a temp dir with $id stripped so
// $RefParser falls back to resolving $refs relative to the file on disk.
async function stripIdsIntoTempDir(): Promise<string> {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "ap2-schemas-"));
  await mkdir(path.join(tempDir, "types"), { recursive: true });

  const topFiles = (await readdir(SCHEMAS_DIR)).filter((f) =>
    f.endsWith(".json")
  );
  for (const file of topFiles) {
    await copyWithoutId(path.join(SCHEMAS_DIR, file), path.join(tempDir, file));
  }
  const typeFiles = (await readdir(TYPES_DIR)).filter((f) =>
    f.endsWith(".json")
  );
  for (const file of typeFiles) {
    await copyWithoutId(
      path.join(TYPES_DIR, file),
      path.join(tempDir, "types", file)
    );
  }
  return tempDir;
}

async function copyWithoutId(src: string, dest: string): Promise<void> {
  const schema = JSON.parse(await readFile(src, "utf8"));
  delete schema.$id;
  await writeFile(dest, JSON.stringify(schema), "utf8");
}

const HEADER = `// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.\n\nimport { z } from 'zod';\n\n`;

// Known gap: json-schema-to-zod (v2.8.1) doesn't support the `contains`
// keyword, so it's silently dropped. Two schemas use it to require "at least
// one array element matching a specific alternative" (open_checkout_mandate's
// `constraints` must contain a line_items entry; open_payment_mandate's
// `constraints` must contain a payment_reference entry). The generated
// validators accept arrays missing that element. See README "Known
// limitations" — flagged rather than silently shipped, since a generic fix
// requires deriving a runtime predicate from an arbitrary $ref'd subschema.

function toPascalCase(fileName: string): string {
  return fileName
    .replace(/\.json$/, "")
    .split(/[_-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

// json-schema-to-zod only reads each `oneOf` branch's `properties` const
// checks and drops each branch's own `required` list when `oneOf` sits next
// to `properties`/`required` on the same object (rather than each branch
// being a fully self-contained alternative schema). AP2's receipt schemas
// use exactly this "oneOf as a sibling constraint" idiom (e.g. a Success
// receipt must additionally require psp_confirmation_id/network_confirmation_id).
// We materialize each branch into a complete object schema — outer
// properties/required merged with the branch's own — which the generator
// already handles correctly for standalone-alternative-schema oneOfs
// elsewhere (e.g. OpenPaymentMandate's constraints union).
function materializeSiblingOneOf(node: unknown): void {
  if (Array.isArray(node)) {
    for (const item of node) materializeSiblingOneOf(item);
    return;
  }
  if (node === null || typeof node !== "object") return;

  const schema = node as Record<string, unknown>;
  if (
    Array.isArray(schema.oneOf) &&
    schema.properties &&
    typeof schema.properties === "object"
  ) {
    const outerProperties = schema.properties as Record<string, unknown>;
    const outerRequired = Array.isArray(schema.required) ? schema.required : [];
    schema.oneOf = (schema.oneOf as Record<string, unknown>[]).map((branch) => {
      const branchProperties = (branch.properties ?? {}) as Record<
        string,
        unknown
      >;
      const branchRequired = Array.isArray(branch.required)
        ? branch.required
        : [];
      return {
        ...branch,
        type: "object",
        properties: { ...outerProperties, ...branchProperties },
        required: [...new Set([...outerRequired, ...branchRequired])],
      };
    });
    delete schema.properties;
    delete schema.required;
  }

  for (const value of Object.values(schema)) materializeSiblingOneOf(value);
}

async function generateFile(
  schemaPath: string,
  outDir: string,
  exportName: string
): Promise<void> {
  // Dereference resolves both relative file $refs (e.g. "types/merchant.json")
  // and internal "#/$defs/..." refs into a single self-contained schema, so
  // each generated file has no cross-file runtime dependency.
  const schema = (await $RefParser.dereference(schemaPath)) as Record<
    string,
    unknown
  >;
  // $id/$schema survive dereferencing but aren't meaningful to json-schema-to-zod.
  delete schema.$id;
  delete schema.$schema;
  materializeSiblingOneOf(schema);

  const zodSource = jsonSchemaToZod(schema, {
    name: `${exportName}Schema`,
    module: "esm",
  });
  const body = zodSource.replace(
    /^import\s*\{\s*z\s*\}\s*from\s*['"]zod['"];?\n*/m,
    ""
  );

  const contents = `${HEADER}${body}\nexport type ${exportName} = z.infer<typeof ${exportName}Schema>;\n`;
  const prettierConfig = await prettier.resolveConfig(outDir);
  const formatted = await prettier.format(contents, {
    ...prettierConfig,
    parser: "typescript",
  });
  await mkdir(outDir, { recursive: true });
  await writeFile(
    path.join(outDir, `${toKebabCase(exportName)}.ts`),
    formatted,
    "utf8"
  );
}

function toKebabCase(pascalCase: string): string {
  return pascalCase.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

async function main(): Promise<void> {
  const tempDir = await stripIdsIntoTempDir();
  try {
    const typeFiles = (await readdir(path.join(tempDir, "types"))).filter((f) =>
      f.endsWith(".json")
    );
    for (const file of typeFiles) {
      const exportName = toPascalCase(file);
      await generateFile(
        path.join(tempDir, "types", file),
        OUT_TYPES_DIR,
        exportName
      );
      console.log(`generated types/${toKebabCase(exportName)}.ts`);
    }

    const mandateFiles = (await readdir(tempDir)).filter((f) =>
      f.endsWith(".json")
    );
    for (const file of mandateFiles) {
      const exportName = toPascalCase(file);
      await generateFile(
        path.join(tempDir, file),
        OUT_MANDATES_DIR,
        exportName
      );
      console.log(`generated mandates/${toKebabCase(exportName)}.ts`);
    }
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
