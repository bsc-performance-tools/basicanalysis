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

/** The command of the report, to copy in browser mode. */
export function paraverCommand(trace, cfg) {
  return `wxparaver "${trace.path}" "cfgs-report/${cfg}"`;
}

/**
 * Open Paraver on a trace with a cfg of cfgs-report/ of the results folder.
 * If the trace is not where results.json says (results copied from the
 * cluster), the user is asked to locate it. Returns the command run.
 */
export async function openParaver(resultsDir, trace, cfg) {
  const call = (path) => invoke('open_paraver', {
    resultsDir, trace: path, traceName: trace.name, cfg,
  });
  try {
    return await call(trace.path);
  } catch (error) {
    if (!String(error).startsWith('TRACE_NOT_FOUND')) throw error;
    const chosen = await open({
      multiple: false, title: `Locate the trace ${trace.name}`,
      filters: [{ name: 'Paraver traces', extensions: ['prv', 'gz'] }],
    });
    if (!chosen) throw new Error(`Trace ${trace.name} not found`);
    return call(chosen);
  }
}
