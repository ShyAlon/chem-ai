export function downloadJSON(filename: string, data: unknown) {
  downloadBlob(filename, new Blob([JSON.stringify(data, null, 2) + '\n'], { type: 'application/json' }));
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
