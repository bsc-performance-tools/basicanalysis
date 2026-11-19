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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![open_results])
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
    fn rejects_other_json_files() {
        let file = std::env::temp_dir().join("ba-desktop-other.json");
        std::fs::write(&file, r#"{"name": "other"}"#).unwrap();
        assert!(open_results(file.to_string_lossy().into_owned()).is_err());
    }
}
