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
