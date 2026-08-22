import workflowData from '../../../src-tauri/workflow/data.json';

export async function readTextFile(path: string): Promise<string> {
  if (path.includes('workflow/data.json')) {
    return JSON.stringify(workflowData);
  }
  return '';
}

export async function copyFile(_source: string, _dest: string): Promise<void> {
  // Storybook mock: no-op
}

export async function readDir(_path: string): Promise<unknown[]> {
  return [];
}

export async function exists(_path: string): Promise<boolean> {
  return false;
}

export async function writeTextFile(_path: string, _contents: string): Promise<void> {
  // Storybook mock: no-op
}

export async function remove(_path: string, _options?: { recursive?: boolean }): Promise<void> {
  // Storybook mock: no-op
}
