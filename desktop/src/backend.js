// Calls to the Rust backend (src-tauri). In a plain browser (prototype mode)
// the backend is not available and the page reads the file itself.
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

export function isTauri() {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/** Ask for a results folder (or a results.json) and read it in the backend. */
export async function openResultsDialog() {
  const path = await open({ directory: true, multiple: false,
                            title: 'Open a BasicAnalysis results folder' });
  if (!path) return null;
  const results = await invoke('open_results', { path });
  return { path, results };
}
