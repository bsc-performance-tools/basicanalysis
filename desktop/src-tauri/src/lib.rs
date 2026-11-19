//! Backend of the BasicAnalysis Analyzer (doc/design/desktop_app.rst).
//!
//! Phase 2: open a BasicAnalysis results folder and return its results.json
//! to the front end. Later phases add the tool adapters (Paraver, Dimemas,
//! Clustering tools), the projects, SSH to the cluster, and MCP.

use std::path::{Path, PathBuf};

const RESULTS_FILE: &str = "results.json";
const SCHEMA: &str = "basicanalysis-results";

/// Path of the results.json of a results folder (or the file itself).
fn results_path(path: &Path) -> PathBuf {
    if path.is_dir() {
        path.join(RESULTS_FILE)
    } else {
        path.to_path_buf()
    }
}

/// Read and check the results.json of a BasicAnalysis results folder.
#[tauri::command]
fn open_results(path: String) -> Result<serde_json::Value, String> {
    let file = results_path(Path::new(&path));
    let text = std::fs::read_to_string(&file).map_err(|error| {
        format!(
            "Cannot read {}: {}. Is this a BasicAnalysis results folder (run with a version that writes results.json)?",
            file.display(),
            error
        )
    })?;
    let results: serde_json::Value = serde_json::from_str(&text)
        .map_err(|error| format!("{} is not valid JSON: {}", file.display(), error))?;
    if results.get("schema").and_then(|s| s.as_str()) != Some(SCHEMA) {
        return Err(format!("{} is not a BasicAnalysis results.json", file.display()));
    }
    Ok(results)
}

/// Find wxparaver: BASICANALYSIS_WXPARAVER, then the PATH, then PARAVER_HOME/bin.
fn find_wxparaver() -> Option<PathBuf> {
    if let Ok(path) = std::env::var("BASICANALYSIS_WXPARAVER") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Some(path);
        }
    }
    if let Some(paths) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&paths) {
            let candidate = dir.join("wxparaver");
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    if let Ok(home) = std::env::var("PARAVER_HOME") {
        let candidate = PathBuf::from(home).join("bin").join("wxparaver");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

/// The trace of a result: its recorded path, or the trace with the same name
/// in the results folder or its parent (results copied from the cluster).
fn resolve_trace(results_dir: &Path, recorded: &str, name: &str) -> Option<PathBuf> {
    let recorded = PathBuf::from(recorded);
    if recorded.is_file() {
        return Some(recorded);
    }
    for dir in [Some(results_dir), results_dir.parent()].into_iter().flatten() {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

/// A cfg of the results folder (cfgs-report/<name>): only a plain file name.
fn report_cfg(results_dir: &Path, cfg: &str) -> Result<PathBuf, String> {
    let name = Path::new(cfg);
    if name.components().count() != 1 || !cfg.ends_with(".cfg") {
        return Err(format!("Invalid cfg name: {}", cfg));
    }
    let path = results_dir.join("cfgs-report").join(name);
    if path.is_file() {
        Ok(path)
    } else {
        Err(format!("{} not found in the results folder", path.display()))
    }
}

/// Open Paraver on a trace with a cfg of the results folder.
///
/// `trace` is the path recorded in results.json, or a path chosen by the
/// user when it was not found. Paraver is started as a separate process
/// (no shell); the command is returned so the user can also run it.
#[tauri::command]
fn open_paraver(results_dir: String, trace: String, trace_name: String, cfg: String)
    -> Result<String, String> {
    let results_dir = results_path(Path::new(&results_dir));
    let results_dir = results_dir.parent().unwrap_or(Path::new(".")).to_path_buf();
    let wxparaver = find_wxparaver().ok_or_else(|| {
        "wxparaver not found: add the Paraver bin folder to the PATH, or set PARAVER_HOME \
         or BASICANALYSIS_WXPARAVER".to_string()
    })?;
    let trace = resolve_trace(&results_dir, &trace, &trace_name)
        .ok_or_else(|| format!("TRACE_NOT_FOUND:{}", trace_name))?;
    let cfg = report_cfg(&results_dir, &cfg)?;
    std::process::Command::new(&wxparaver)
        .arg(&trace)
        .arg(&cfg)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map_err(|error| format!("Cannot start {}: {}", wxparaver.display(), error))?;
    Ok(format!("{} \"{}\" \"{}\"", wxparaver.display(), trace.display(), cfg.display()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![open_results, open_paraver])
        .run(tauri::generate_context!())
        .expect("error while running the BasicAnalysis Analyzer");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opens_the_results_of_a_folder() {
        let dir = std::env::temp_dir().join("ba-desktop-test");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join(RESULTS_FILE),
            r#"{"schema": "basicanalysis-results", "schema_version": 1}"#,
        )
        .unwrap();
        let results = open_results(dir.to_string_lossy().into_owned()).unwrap();
        assert_eq!(results["schema_version"], 1);
    }

    #[test]
    fn report_cfg_accepts_only_plain_names() {
        let dir = std::env::temp_dir().join("ba-desktop-cfg");
        std::fs::create_dir_all(dir.join("cfgs-report")).unwrap();
        std::fs::write(dir.join("cfgs-report").join("useful_duration.cfg"), "").unwrap();
        assert!(report_cfg(&dir, "useful_duration.cfg").is_ok());
        assert!(report_cfg(&dir, "../../etc/passwd").is_err());
        assert!(report_cfg(&dir, "/etc/passwd.cfg").is_err());
        assert!(report_cfg(&dir, "missing.cfg").is_err());
    }

    #[test]
    fn trace_found_next_to_the_results() {
        let dir = std::env::temp_dir().join("ba-desktop-trace");
        let results = dir.join("results");
        std::fs::create_dir_all(&results).unwrap();
        std::fs::write(dir.join("app.prv"), "").unwrap();
        let found = resolve_trace(&results, "/cluster/path/app.prv", "app.prv").unwrap();
        assert_eq!(found, dir.join("app.prv"));
        assert!(resolve_trace(&results, "/cluster/path/x.prv", "x.prv").is_none());
    }

    #[test]
    fn rejects_other_json_files() {
        let file = std::env::temp_dir().join("ba-desktop-other.json");
        std::fs::write(&file, r#"{"name": "other"}"#).unwrap();
        assert!(open_results(file.to_string_lossy().into_owned()).is_err());
    }
}
