export async function resolveResource(resourcePath: string): Promise<string> {
  return `/mock/resources/${resourcePath}`;
}

export async function appDataDir(): Promise<string> {
  return '/mock/app/data';
}

export async function homeDir(): Promise<string> {
  return '/mock/home';
}

export function join(...paths: string[]): string {
  return paths.join('/').replace(/\/+/g, '/');
}

export async function basename(path: string): Promise<string> {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

export async function dirname(path: string): Promise<string> {
  const normalized = path.replace(/\\/g, '/');
  const end = normalized.lastIndexOf('/');
  return end < 0 ? '.' : normalized.slice(0, end) || '/';
}
