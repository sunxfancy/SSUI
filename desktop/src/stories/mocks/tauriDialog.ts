export async function open(options?: { directory?: boolean; multiple?: boolean }): Promise<string | string[] | null> {
  if (options?.directory) {
    return 'C:/Users/demo/Documents/Projects';
  }
  return null;
}
