/**
 * Environment Variable Validation
 * Validates required environment variables and provides helpful error messages
 */

type EnvVar = {
  key: string;
  required: boolean;
  description: string;
  defaultValue?: string;
};

const ENV_VARS: EnvVar[] = [
  {
    key: "NEXT_PUBLIC_API_BASE_URL",
    required: false,
    description: "Base URL for API requests (can be relative or absolute)",
    defaultValue: "/api/backend",
  },
  {
    key: "NEXT_PUBLIC_API_PORT",
    required: false,
    description: "API port number",
    defaultValue: "8000",
  },
  {
    key: "BACKEND_API_BASE_URL",
    required: false,
    description: "Direct backend URL (server-side only)",
    defaultValue: "http://localhost:8000",
  },
  {
    key: "NEXT_PUBLIC_APP_BASE_URL",
    required: false,
    description: "App base URL",
    defaultValue: "http://localhost:4000",
  },
  {
    key: "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
    required: false,
    description: "Google OAuth Client ID (optional - for Google Sign-In)",
  },
  {
    key: "NEXT_PUBLIC_GOOGLE_REDIRECT_URI",
    required: false,
    description: "Google OAuth Redirect URI",
  },
];

class EnvValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvValidationError";
  }
}

export function validateEnv(): void {
  const errors: string[] = [];
  const warnings: string[] = [];

  ENV_VARS.forEach(({ key, required, description, defaultValue }) => {
    const value = process.env[key];

    if (required && !value) {
      errors.push(`Missing required environment variable: ${key} - ${description}`);
    } else if (!value && defaultValue) {
      warnings.push(
        `Environment variable ${key} not set. Using default: ${defaultValue} - ${description}`
      );
    }
  });

  if (errors.length > 0) {
    throw new EnvValidationError(
      `Environment validation failed:\n${errors.join("\n")}`
    );
  }

  if (warnings.length > 0 && process.env.NODE_ENV !== "production") {
    console.warn("Environment warnings:");
    warnings.forEach((warning) => console.warn(`  - ${warning}`));
  }
}

export function getEnv(key: string, fallback?: string): string {
  const value = process.env[key];
  if (!value && !fallback) {
    throw new EnvValidationError(
      `Required environment variable not found: ${key}`
    );
  }
  return value || fallback || "";
}

// Validate on module load (only in development)
if (process.env.NODE_ENV !== "production") {
  try {
    validateEnv();
  } catch (error) {
    console.error(error);
    // Don't throw in development - just warn
  }
}
