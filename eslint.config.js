import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';
import tsParser from '@typescript-eslint/parser';
import cypress from 'eslint-plugin-cypress/flat';
import globals from 'globals';

export default [
	{
		ignores: ['build/*', '**/pyodide/*', '**/.venv/*', '**/.svelte-kit/*']
	},
	js.configs.recommended,
	...tseslint.configs.recommended,
	...svelte.configs['flat/recommended'],
	cypress.configs.recommended,
	{
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: {
				...globals.browser,
				...globals.es2017,
				...globals.node
			}
		}
	},
	{
		files: ['**/*.svelte', '*.svelte'],
		languageOptions: {
			parser: svelteParser,
			parserOptions: {
				parser: tsParser
			}
		}
	}
];
