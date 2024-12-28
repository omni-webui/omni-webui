import { writeFile } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { paraglide } from "@inlang/paraglide-js-adapter-sveltekit/vite";
import { sveltekit } from "@sveltejs/kit/vite";
import { loadPyodide } from "pyodide";
import { defineConfig, normalizePath } from "vite";
import { viteStaticCopy } from "vite-plugin-static-copy";
import ClosePlugin from "./vite-plugin-close";

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
				src: [normalizePath(join(pyodideDir, "*"))].concat(PYODIDE_EXCLUDE),
				dest: "pyodide",
			},
		],
	});
}

// https://vite.dev/config/
export default defineConfig({
	optimizeDeps: { exclude: ["pyodide"] },
	plugins: [
		paraglide({
			project: "./project.inlang", //Path to your inlang project
			outdir: "./src/lib/paraglide", //Where you want the generated files to be placed
		}),
		sveltekit(),
		viteStaticCopyPyodide(),
		ClosePlugin(), // ridiculous bug, solution from https://stackoverflow.com/a/76920975/5434822
	],
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
