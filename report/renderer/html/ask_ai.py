"""Ask AI: copy a question about the report, with its context, for an AI
assistant (prototype of phase 1 of doc/design/ai_assistance.rst).

The context is built in the browser from what the report already contains:
the efficiency tables (values and thresholds of each cell) and the Metric
Details data of each metric (definition, formula, interpretation, causes,
next steps). Nothing is sent anywhere: the analyst copies or downloads the
text and pastes it into the assistant of their choice. No API key is needed.
"""

ASK_AI_BUTTON_LABEL = "Ask AI"


def ask_ai_nav_button_html():
    """Button of the navigation bar: ask about the view or the analysis."""

    return """
        <button
            type="button"
            class="ba-ask-ai-nav-button"
            onclick="baAskAi('view')"
            aria-haspopup="dialog"
            title="Ask an AI assistant about this view (copies the question
with the metrics and their definitions)"
        >
            <span aria-hidden="true">&#10024;</span> Ask AI
        </button>
    """


def ask_ai_metric_button_html():
    """Button of the Metric Details dialog: ask about the metric shown."""

    return """
        <div class="metric-details-section ba-ask-ai-metric">
            <button
                type="button"
                class="ba-ask-ai-metric-button"
                onclick="baAskAi('metric')"
                aria-haspopup="dialog"
            >
                <span aria-hidden="true">&#10024;</span>
                Ask AI about this metric
            </button>
        </div>
    """


def ask_ai_html():
    """Dialog, styles, and script of Ask AI, added once to the report."""

    return _DIALOG + _STYLE + _SCRIPT


_DIALOG = """
<div id="ba-ask-ai" class="ba-ask-ai" hidden>
    <div class="ba-ask-ai-backdrop" onclick="baAskAiClose()"></div>
    <section class="ba-ask-ai-dialog" role="dialog" aria-modal="true"
             aria-labelledby="ba-ask-ai-title">
        <button type="button" class="ba-ask-ai-close"
                aria-label="Close" onclick="baAskAiClose()">&times;</button>
        <div class="ba-ask-ai-eyebrow">Ask AI</div>
        <h2 id="ba-ask-ai-title">Ask an AI assistant</h2>
        <p class="ba-ask-ai-intro">
            The text below contains your question, the metrics, and their
            definitions. Copy it and paste it into the AI assistant you
            choose. Nothing is sent from the report.
        </p>

        <label class="ba-ask-ai-label" for="ba-ask-ai-scope">About</label>
        <select id="ba-ask-ai-scope" onchange="baAskAiRefresh(true)">
            <option value="metric">This metric</option>
            <option value="view">This view</option>
            <option value="analysis">The whole analysis</option>
        </select>

        <label class="ba-ask-ai-label" for="ba-ask-ai-question">Question</label>
        <textarea id="ba-ask-ai-question" rows="3"
                  oninput="baAskAiRefresh(false)"></textarea>

        <label class="ba-ask-ai-check">
            <input type="checkbox" id="ba-ask-ai-names"
                   onchange="baAskAiRefresh(false)">
            Include trace file names and the command line
        </label>

        <details class="ba-ask-ai-preview">
            <summary>Text to copy <span id="ba-ask-ai-size"></span></summary>
            <pre id="ba-ask-ai-text"></pre>
        </details>

        <div class="ba-ask-ai-actions">
            <button type="button" class="ba-ask-ai-primary"
                    onclick="baAskAiCopy()">Copy</button>
            <button type="button" onclick="baAskAiDownload()">Download (.md)</button>
            <span id="ba-ask-ai-status" class="ba-ask-ai-status"
                  role="status"></span>
        </div>
    </section>
</div>
"""

_STYLE = """
<style>
.ba-ask-ai-nav-button {
    height: 34px;
    margin-right: 6px;
    padding: 0 12px;
    border: 1px solid #aabed2;
    border-radius: 7px;
    background: #ffffff;
    color: #1f3550;
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}
.ba-ask-ai-nav-button:hover,
.ba-ask-ai-metric-button:hover { background: #eef3f9; }
.ba-ask-ai-metric-button {
    padding: 6px 12px;
    border: 1px solid #aabed2;
    border-radius: 7px;
    background: #ffffff;
    color: #1f3550;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
}
.ba-ask-ai[hidden] { display: none; }
.ba-ask-ai {
    position: fixed;
    inset: 0;
    z-index: 2000;
    display: grid;
    place-items: center;
}
.ba-ask-ai-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(15, 30, 50, 0.45);
}
.ba-ask-ai-dialog {
    position: relative;
    width: min(760px, calc(100vw - 32px));
    max-height: calc(100vh - 48px);
    overflow: auto;
    padding: 20px 22px;
    border-radius: 12px;
    background: #ffffff;
    color: #1d2733;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.25);
    font-size: 14px;
}
.ba-ask-ai-close {
    position: absolute;
    top: 10px;
    right: 12px;
    border: 0;
    background: transparent;
    font-size: 22px;
    cursor: pointer;
}
.ba-ask-ai-eyebrow {
    color: #5c677a;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.ba-ask-ai-dialog h2 { margin: 2px 0 6px; font-size: 20px; }
.ba-ask-ai-intro { margin: 0 0 12px; color: #5c677a; }
.ba-ask-ai-label {
    display: block;
    margin: 10px 0 4px;
    font-weight: 600;
}
.ba-ask-ai-dialog select,
.ba-ask-ai-dialog textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 6px 8px;
    border: 1px solid #c4d0de;
    border-radius: 6px;
    font: inherit;
}
.ba-ask-ai-check {
    display: block;
    margin: 10px 0;
    color: #5c677a;
    font-size: 13px;
}
.ba-ask-ai-preview summary { cursor: pointer; font-weight: 600; }
.ba-ask-ai-preview pre {
    max-height: 300px;
    overflow: auto;
    padding: 10px;
    border-radius: 6px;
    background: #f4f6f9;
    font-size: 11px;
    white-space: pre-wrap;
}
#ba-ask-ai-size { color: #5c677a; font-weight: 400; }
.ba-ask-ai-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
}
.ba-ask-ai-actions button {
    padding: 6px 14px;
    border: 1px solid #aabed2;
    border-radius: 6px;
    background: #ffffff;
    font: inherit;
    cursor: pointer;
}
.ba-ask-ai-actions .ba-ask-ai-primary {
    border-color: #1f4e79;
    background: #1f4e79;
    color: #ffffff;
}
.ba-ask-ai-status { color: #2e7d32; font-size: 13px; }
@media print {
    .ba-ask-ai-nav-button, .ba-ask-ai-metric, .ba-ask-ai { display: none; }
}
</style>
"""

_SCRIPT = r"""
<script>
(function () {
    "use strict";

    var state = {metric: null, view: null};

    // ------------------------------------------------------------------
    // Metric Details: remember the metric that was opened.
    // ------------------------------------------------------------------
    function wrapSelectMetricCell() {
        var original = window.selectMetricCell;
        if (typeof original !== "function" || original.baWrapped) { return; }
        var wrapped = function (trigger, sectionId, metricKey, metricLabel,
                                traceLabel, value) {
            state.metric = {trigger: trigger, section: sectionId,
                            key: metricKey, label: metricLabel,
                            trace: traceLabel, value: value};
            return original.apply(this, arguments);
        };
        wrapped.baWrapped = true;
        window.selectMetricCell = wrapped;
    }

    // ------------------------------------------------------------------
    // Reading the report
    // ------------------------------------------------------------------
    function text(element) {
        return (element ? element.textContent : "")
            .replace(/\s+/g, " ").replace(/[↳⚠]/g, "").trim();
    }

    function info(section, key) {
        var dict = window["metricInfo_" + section];
        return dict ? dict[key] : null;
    }

    function status(cell) {
        var value = parseFloat(cell.getAttribute("data-value"));
        if (!isFinite(value)) { return ""; }
        var own = {critical: parseFloat(cell.getAttribute("data-critical")),
                   attention: parseFloat(cell.getAttribute("data-attention")),
                   reference: parseFloat(cell.getAttribute("data-reference"))};
        var t = window.effectiveThresholds
            ? window.effectiveThresholds(own, cell) : own;
        if (value > t.reference) { return "above reference"; }
        if (value < t.critical) { return "Critical"; }
        if (value < t.attention) { return "Attention"; }
        return "Good";
    }

    function activeViewId() {
        var root = document.querySelector("[data-guided-analysis-navigation]");
        return root ? root.getAttribute("data-active-primary-view") : null;
    }

    function viewArticle(id) {
        return document.querySelector(
            "article[data-guided-view-id='" + id + "']");
    }

    function viewTitle(article) {
        return article.getAttribute("data-guided-view-title")
            || article.getAttribute("data-guided-view-id");
    }

    // One efficiency table as Markdown, and the metrics it contains.
    function readTable(table) {
        var headers = Array.prototype.map.call(
            table.querySelectorAll("thead th"), text);
        var lines = ["| " + headers.join(" | ") + " |",
                     "|" + headers.map(function () { return "---"; })
                         .join("|") + "|"];
        var metrics = [];
        Array.prototype.forEach.call(
            table.querySelectorAll("tbody tr"), function (row) {
                var nameCell = row.querySelector(".metric-name-cell");
                if (!nameCell) { return; }
                var depth = parseInt(
                    nameCell.style.getPropertyValue("--metric-depth") || "0",
                    10) || 0;
                var name = new Array(depth + 1).join("  ")
                    + (depth ? "- " : "") + text(nameCell);
                if (nameCell.querySelector(".workload-mark")) {
                    name += " [workload ratio]";
                }
                var cells = [name];
                var metric = null;
                var statuses = [];
                Array.prototype.forEach.call(
                    row.querySelectorAll(".metric-value-cell"),
                    function (td) {
                        var button = td.querySelector(".metric-value");
                        if (!button) { cells.push(text(td)); return; }
                        var s = status(button);
                        statuses.push(s);
                        cells.push(text(button) + (s ? " (" + s + ")" : ""));
                        metric = metric || {
                            key: button.getAttribute("data-metric-key"),
                            section: button.getAttribute("data-section")
                        };
                    });
                lines.push("| " + cells.join(" | ") + " |");
                if (metric && metric.key) {
                    metric.statuses = statuses;
                    metrics.push(metric);
                }
            });
        return {header: headers[0] || "", markdown: lines.join("\n"),
                metrics: metrics};
    }

    function viewTables(article) {
        return Array.prototype.map.call(
            article.querySelectorAll("table.efficiency-table"), readTable);
    }

    // A plain table (trace configuration, general metrics) as Markdown.
    function plainTable(table, dropColumns) {
        var rows = Array.prototype.map.call(
            table.querySelectorAll("tr"), function (tr) {
                return Array.prototype.map.call(
                    tr.querySelectorAll("th, td"), text);
            });
        if (!rows.length) { return ""; }
        var drop = rows[0].map(function (h) {
            return dropColumns.indexOf(h) >= 0;
        });
        var keep = function (row) {
            return row.filter(function (_, i) { return !drop[i]; });
        };
        var width = keep(rows[0]).length;
        return rows.map(function (row, i) {
            var cells = keep(row);
            while (cells.length < width) { cells.push(""); }
            var line = "| " + cells.join(" | ") + " |";
            return i === 0
                ? line + "\n|" + cells.map(function () { return "---"; })
                    .join("|") + "|"
                : line;
        }).join("\n");
    }

    // ------------------------------------------------------------------
    // Context
    // ------------------------------------------------------------------
    var INSTRUCTIONS = [
        "You are helping a performance analyst interpret POP efficiency",
        "metrics computed by BasicAnalysis (BSC) from Paraver traces.",
        "",
        "- Base your answer on the metric values and the definitions given",
        "  below; cite the metric names and values you rely on.",
        "- Efficiencies are percentages; 100% is ideal. Scalability metrics",
        "  are relative to the first trace (the reference).",
        "- The metrics form a multiplicative hierarchy: a parent is the",
        "  product of its children (indented rows).",
        "- Each value is classified as Critical, Attention, or Good with the",
        "  thresholds given.",
        "- Say when the data is not enough to conclude, and what should be",
        "  measured or inspected to find out.",
        "- Suggest the next steps: the Paraver views or BasicAnalysis views",
        "  to inspect, and what to look for in them."
    ].join("\n");

    function executionSection(includeNames) {
        var parts = ["## Execution"];
        var overview = viewArticle("overview");
        if (overview) {
            var mode = overview.querySelector(".trace-mode-tag");
            if (mode) { parts.push(text(mode)); }
            if (includeNames) {
                var command = overview.querySelector(".report-command");
                if (command) { parts.push(text(command)); }
            }
            var tables = overview.querySelectorAll("table.metric-table");
            if (tables.length) {
                parts.push("Trace configuration:\n\n" + plainTable(
                    tables[0], includeNames ? [] : ["Trace"]));
            }
            var general = Array.prototype.filter.call(tables, function (t) {
                return /Elapsed time/.test(t.textContent);
            })[0];
            if (general) {
                parts.push("General metrics:\n\n" + plainTable(general, []));
            }
        }
        var scaling = document.querySelector("table.scaling-levels");
        if (scaling) {
            parts.push("Scaling model:\n\n" + plainTable(scaling, []));
        }
        var columns = document.querySelector(".trace-header-note code");
        if (columns) {
            parts.push("Trace columns: " + text(columns));
        }
        return parts.join("\n\n");
    }

    function definitionText(metric) {
        var data = info(metric.section, metric.key);
        if (!data) { return ""; }
        var lines = ["### " + (data.title || metric.key)];
        if (data.definition) { lines.push("Definition: " + data.definition); }
        if (data.formula) { lines.push("Formula: " + data.formula); }
        var interp = data.interpretation || {};
        if (interp.low) { lines.push("Low values: " + interp.low); }
        if (interp.high) { lines.push("High values: " + interp.high); }
        if (interp.above_reference) {
            lines.push("Above 100%: " + interp.above_reference);
        }
        if (data.causes && data.causes.length) {
            lines.push("Possible causes: " + data.causes.join("; "));
        }
        if (data.recommendations && data.recommendations.length) {
            lines.push("Next steps: " + data.recommendations.join(" "));
        }
        var t = data.thresholds;
        if (t) {
            lines.push("Thresholds: Critical below " + t.critical
                + "%, Good from " + t.attention + "%.");
        }
        return lines.map(function (line) {
            return line.replace(/\s+/g, " ").trim();
        }).join("\n");
    }

    function notGood(metric) {
        return metric.statuses.some(function (s) {
            return s === "Critical" || s === "Attention";
        });
    }

    function definitions(metrics, always) {
        var seen = {};
        var chosen = metrics.filter(function (m) {
            var wanted = notGood(m) || (always && always(m));
            if (!wanted || seen[m.key]) { return false; }
            seen[m.key] = true;
            return true;
        });
        if (!chosen.length) { chosen = metrics.slice(0, 3); }
        return chosen.map(definitionText).filter(Boolean).join("\n\n");
    }

    // Views of the whole analysis, without duplicates of the Host and
    // Device tables (shown in the Heterogeneous Model view).
    function analysisArticles() {
        var skip = ["overview", "computation-scalability"];
        if (viewArticle("execution-domains")) {
            skip.push("host-analysis", "device-analysis");
        }
        return Array.prototype.filter.call(
            document.querySelectorAll("article[data-guided-view-id]"),
            function (a) {
                return skip.indexOf(a.getAttribute("data-guided-view-id")) < 0;
            });
    }

    function metricsSection(scope) {
        var blocks = [];
        var metrics = [];
        var always = null;

        if (scope === "metric" && state.metric) {
            var cell = state.metric.trigger;
            var table = cell && cell.closest("table.efficiency-table");
            var article = cell && cell.closest("article[data-guided-view-id]");
            var read = table ? readTable(table) : null;
            if (read) {
                blocks.push("## Metrics (" + (article ? viewTitle(article) + ", "
                    : "") + read.header + ")\n\nThe question is about **"
                    + state.metric.label + "** in the configuration **"
                    + state.metric.trace + "**.\n\n" + read.markdown);
                metrics = read.metrics;
            }
            var key = state.metric.key;
            always = function (m) { return m.key === key; };
            // The selected metric first in the definitions.
            metrics.sort(function (a, b) {
                return (b.key === key) - (a.key === key);
            });
        } else {
            var articles = scope === "view"
                ? [viewArticle(state.view)].filter(Boolean)
                : analysisArticles();
            articles.forEach(function (article) {
                viewTables(article).forEach(function (read) {
                    var title = viewTitle(article);
                    blocks.push("## " + (read.header && read.header !== title
                        ? title + " — " + read.header : title)
                        + "\n\n" + read.markdown);
                    metrics = metrics.concat(read.metrics);
                });
            });
        }

        if (!blocks.length) {
            blocks.push("## Metrics\n\n(No efficiency table in this view.)");
        }
        var defs = definitions(metrics, always);
        return blocks.join("\n\n") + (defs
            ? "\n\n## Definitions of the metrics to examine\n\n" + defs : "");
    }

    function defaultQuestion(scope) {
        if (scope === "metric" && state.metric) {
            return "Why is " + state.metric.label + " "
                + (state.metric.value === null ? "not available"
                   : state.metric.value.toFixed(2) + "%")
                + " in the " + state.metric.trace + " configuration, and"
                + " what should I look at next to find the cause?";
        }
        if (scope === "view") {
            return "Which metrics of this view indicate the main efficiency"
                + " losses, what are their likely causes, and what should I"
                + " look at next?";
        }
        return "What are the main performance issues of this application,"
            + " in order of importance, and which analyses should I do next"
            + " to confirm their causes?";
    }

    function buildText() {
        var scope = document.getElementById("ba-ask-ai-scope").value;
        var question = document.getElementById("ba-ask-ai-question").value;
        var names = document.getElementById("ba-ask-ai-names").checked;
        return [
            "# Question about a BasicAnalysis performance report",
            INSTRUCTIONS,
            executionSection(names),
            metricsSection(scope),
            "## Question\n\n" + question
        ].join("\n\n") + "\n";
    }

    // ------------------------------------------------------------------
    // Dialog
    // ------------------------------------------------------------------
    window.baAskAiRefresh = function (newScope) {
        if (newScope) {
            document.getElementById("ba-ask-ai-question").value =
                defaultQuestion(document.getElementById("ba-ask-ai-scope").value);
        }
        var content = buildText();
        document.getElementById("ba-ask-ai-text").textContent = content;
        document.getElementById("ba-ask-ai-size").textContent =
            "(" + Math.round(content.length / 100) / 10 + " K characters)";
        document.getElementById("ba-ask-ai-status").textContent = "";
    };

    window.baAskAi = function (scope) {
        wrapSelectMetricCell();
        state.view = activeViewId();
        if (scope === "view" && state.view === "overview") {
            scope = "analysis";
        }
        var select = document.getElementById("ba-ask-ai-scope");
        select.querySelector("option[value='metric']").disabled = !state.metric;
        if (scope === "metric" && !state.metric) { scope = "view"; }
        select.value = scope;
        if (typeof window.closeMetricDetails === "function"
                && scope === "metric") {
            window.closeMetricDetails();
        }
        window.baAskAiRefresh(true);
        var dialog = document.getElementById("ba-ask-ai");
        dialog.hidden = false;
        document.getElementById("ba-ask-ai-question").focus();
    };

    window.baAskAiClose = function () {
        document.getElementById("ba-ask-ai").hidden = true;
    };

    function done(message) {
        document.getElementById("ba-ask-ai-status").textContent = message;
    }

    window.baAskAiCopy = function () {
        var content = buildText();
        function fallback() {
            var area = document.createElement("textarea");
            area.value = content;
            document.body.appendChild(area);
            area.select();
            try {
                document.execCommand("copy");
                done("Copied. Paste it into your AI assistant.");
            } catch (error) {
                done("Copy failed: use Download.");
            }
            document.body.removeChild(area);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(content).then(function () {
                done("Copied. Paste it into your AI assistant.");
            }, fallback);
        } else {
            fallback();
        }
    };

    window.baAskAiDownload = function () {
        var blob = new Blob([buildText()], {type: "text/markdown"});
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "basicanalysis-question.md";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        done("Downloaded basicanalysis-question.md.");
    };

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") { window.baAskAiClose(); }
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", wrapSelectMetricCell);
    } else {
        wrapSelectMetricCell();
    }
})();
</script>
"""
