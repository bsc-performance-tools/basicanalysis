import unittest

from report.renderer.html.ask_ai import (
    ask_ai_html,
    ask_ai_metric_button_html,
    ask_ai_nav_button_html,
)


class AskAiMarkupTests(unittest.TestCase):

    def test_buttons_open_the_dialog(self):
        self.assertIn("baAskAi('view')", ask_ai_nav_button_html())
        self.assertIn("baAskAi('metric')", ask_ai_metric_button_html())

    def test_dialog_and_script(self):
        page = ask_ai_html()
        for element in ("ba-ask-ai-scope", "ba-ask-ai-question",
                        "ba-ask-ai-names", "ba-ask-ai-text"):
            self.assertIn('id="{}"'.format(element), page)
        self.assertIn("window.baAskAi =", page)
        self.assertIn("window.baAskAiCopy", page)
        # Nothing is sent: no network calls in the script.
        for call in ("fetch(", "XMLHttpRequest", "sendBeacon"):
            self.assertNotIn(call, page)

    def test_value_cells_carry_the_metric_key(self):
        import interactiveplots as ip
        table = ip._build_efficiency_table_html(
            metric_keys=["parallel_eff"],
            metric_info={"parallel_eff": {"label": "Parallel efficiency"}},
            metric_sources={"parallel_eff": {"t.prv": 80.0}},
            trace_list=["t.prv"],
            trace_labels=["2"],
            section_id="global",
        )
        self.assertIn("data-metric-key='parallel_eff'", table)
        self.assertIn("data-section='global'", table)


if __name__ == "__main__":
    unittest.main()
