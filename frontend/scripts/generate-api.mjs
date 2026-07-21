import fs from "node:fs/promises";
import path from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const frontendRoot = path.resolve(import.meta.dirname, "..");
const schemaUrl = process.env.OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json";
const schemaPath = path.join(frontendRoot, "openapi.json");
const outputPath = path.join(frontendRoot, "src", "api", "generated", "schema.d.ts");

const response = await fetch(schemaUrl);
if (!response.ok) {
  throw new Error(`Failed to fetch OpenAPI schema from ${schemaUrl}: ${response.status}`);
}

const schema = await response.json();
await fs.writeFile(schemaPath, `${JSON.stringify(schema, null, 2)}\n`, "utf8");

const ast = await openapiTS(schema, {
  alphabetize: true,
  exportType: true
});

await fs.writeFile(outputPath, `${astToString(ast).trimEnd()}\n`, "utf8");
console.log(`OpenAPI snapshot saved to ${schemaPath}`);
console.log(`Generated schema types saved to ${outputPath}`);
