import { writeFile } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sveltekit } from "@sveltejs/kit/vite";
import { loadPyodide } from "pyodide";
import { defineConfig } from "vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

const PYODIDE_EXCLUDE = ["!**/*.{md,html}", "!**/*.d.ts", "!**/node_modules"];
const packages = [
	"micropip",
	"packaging",
	"requests",
	"beautifulsoup4",
	"numpy",
	"pandas",
	"matplotlib",
	"scikit-learn",
	"scipy",
	"regex",
	"seaborn",
];
export async function viteStaticCopyPyodide() {
	const pyodide = await loadPyodide();
	await pyodide.loadPackage("micropip");
	const micropip = pyodide.pyimport("micropip");
	const pyodideDir = dirname(fileURLToPath(import.meta.resolve("pyodide")));
	for (const pkg of packages) {
		await micropip.install(pkg);
	}
	const lockfile = await micropip.freeze();
	await writeFile(
		join(pyodideDir, "pyodide-lock.json"),
		lockfile,
		"utf-8",
		() => {},
	);
	return viteStaticCopy({
		targets: [
			{
				src: [join(pyodideDir, "*")].concat(PYODIDE_EXCLUDE),
				dest: "pyodide",
			},
		],
	});
}

// https://vite.dev/config/
export default defineConfig({
	optimizeDeps: { exclude: ["pyodide"] },
	plugins: [sveltekit(), viteStaticCopyPyodide()],
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || "dev-build"),
	},
	build: {
		sourcemap: true,
	},
	worker: {
		format: "es",
	},
});
