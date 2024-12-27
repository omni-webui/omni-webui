import { browser, dev } from "$app/environment";
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./v1";

const apiKey = browser ? localStorage.getItem("api-key") : "";
const UNPROTECTED_ROUTES = ["/api/v1/auth/signin", "/api/v1/auth/signup"];
const authMiddleware: Middleware = {
	onRequest({ schemaPath, request }) {
		if (
			UNPROTECTED_ROUTES.some((pathname) => schemaPath.startsWith(pathname))
		) {
			return undefined; // don’t modify request for certain paths
		}
		// for all other paths, set Authorization header as expected
		request.headers.set("Authorization", `Bearer ${apiKey}`);
		return request;
	},
};

export const client = createClient<paths>({
	baseUrl: dev ? "http://localhost:8080" : "",
});
client.use(authMiddleware);

export default client;
