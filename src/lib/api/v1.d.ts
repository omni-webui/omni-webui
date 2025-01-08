/**
 * This file was auto-generated by openapi-typescript.
 * Do not make direct changes to the file.
 */

export interface paths {
    "/api/v1/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Users */
        get: operations["list_users_api_v1_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/files": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Files */
        get: operations["list_files_api_v1_files_get"];
        put?: never;
        /** Upload File */
        post: operations["upload_file_api_v1_files_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/mcp/servers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Retrieve Servers */
        get: operations["retrieve_servers_mcp_servers_get"];
        put?: never;
        /** Create Server */
        post: operations["create_server_mcp_servers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Healthcheck */
        get: operations["healthcheck_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/db": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Healthcheck With Db */
        get: operations["healthcheck_with_db_health_db_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AsyncCursorPage[FileObject] */
        AsyncCursorPage_FileObject_: {
            /** Data */
            data: components["schemas"]["FileObject"][];
        } & {
            [key: string]: unknown;
        };
        /** Body_upload_file_api_v1_files_post */
        Body_upload_file_api_v1_files_post: {
            /**
             * File
             * Format: binary
             */
            file: string;
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "assistants" | "batch" | "fine-tune" | "vision";
        };
        /** FileObject */
        FileObject: {
            /** Id */
            id: string;
            /** Bytes */
            bytes: number;
            /** Created At */
            created_at: number;
            /** Filename */
            filename: string;
            /**
             * Object
             * @constant
             */
            object: "file";
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "assistants" | "assistants_output" | "batch" | "batch_output" | "fine-tune" | "fine-tune-results" | "vision";
            /**
             * Status
             * @enum {string}
             */
            status: "uploaded" | "processed" | "error";
            /** Status Details */
            status_details?: string | null;
        } & {
            [key: string]: unknown;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ServerParams */
        ServerParams: {
            /** Mcpservers */
            mcpServers: {
                [key: string]: components["schemas"]["StdioServerParameters"];
            };
        };
        /** Settings */
        Settings: {
            /**
             * Title
             * @default Omni WebUI
             */
            title: string;
            /** Secret Key */
            secret_key?: string;
            /** Frontend Dir */
            frontend_dir?: string;
            /**
             * Data Dir
             * @default /Users/tcztzy/Library/Application Support/omni-webui
             */
            data_dir: string;
            /**
             * Database Url
             * @default
             */
            database_url: string;
            /** Mcpservers */
            mcpServers?: {
                [key: string]: components["schemas"]["StdioServerParameters"];
            };
        };
        /** StdioServerParameters */
        StdioServerParameters: {
            /** Command */
            command: string;
            /** Args */
            args?: string[];
            /** Env */
            env?: {
                [key: string]: string;
            } | null;
            /**
             * Encoding
             * @default utf-8
             */
            encoding: string;
            /**
             * Encoding Error Handler
             * @default strict
             * @enum {string}
             */
            encoding_error_handler: "strict" | "ignore" | "replace";
        };
        /**
         * User
         * @description User model.
         */
        User: {
            /** Id */
            id?: string;
            /** Name */
            name: string;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Role
             * @default pending
             */
            role: string;
            /**
             * Profile Image Url
             * @default /user.png
             */
            profile_image_url: string;
            /** Last Active At */
            last_active_at?: number;
            /** Updated At */
            updated_at?: number;
            /** Created At */
            created_at?: number;
            /** Api Key */
            api_key?: string | null;
            settings?: components["schemas"]["UserSettings"] | null;
            /** Info */
            info?: Record<string, never> | null;
            /** Oauth Sub */
            oauth_sub?: string | null;
        };
        /**
         * UserSettings
         * @description User settings model.
         */
        UserSettings: {
            /** Ui */
            ui?: Record<string, never>;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_users_api_v1_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["User"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_files_api_v1_files_get: {
        parameters: {
            query?: {
                after?: string | null;
                limit?: number;
                order?: "asc" | "desc";
                purpose?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: {
                token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AsyncCursorPage_FileObject_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_file_api_v1_files_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                token?: string | null;
            };
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_file_api_v1_files_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FileObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retrieve_servers_mcp_servers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Settings"];
                };
            };
        };
    };
    create_server_mcp_servers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServerParams"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Settings"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    healthcheck_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    healthcheck_with_db_health_db_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
