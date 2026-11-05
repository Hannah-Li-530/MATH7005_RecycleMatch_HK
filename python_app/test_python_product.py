"""Python unit and native-UI checks for the final submission entrypoint.

Contribution: AI-assisted tests; team must record actual review ownership in
CONTRIBUTIONS.md. Network geocoding is tested separately from UI simulation.
"""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from rewards_model import green_estimate, cash_estimate, budget_rewards, RATES
from recycling_service import query_plan, compare_plans, search_places, place_coordinates

APP = Path(__file__).with_name("course_app.py")


class PythonProductTests(unittest.TestCase):
    def test_reward_budget_and_priority(self):
        earned = green_estimate(list(RATES)[0], 10)
        self.assertEqual(earned, 800)
        total, ready, future = budget_rewards(400, earned)
        self.assertEqual(total, 1200)
        self.assertEqual(ready[0]["points"], 1000)
        self.assertEqual(future[0]["gap"], 800)
        self.assertEqual(green_estimate(list(RATES)[0], .09), 0)
        self.assertEqual(cash_estimate(100), (Decimal("3.00"), 30))
        for value in [-1, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                budget_rewards(value, 0)
        with self.assertRaises(ValueError):
            green_estimate(list(RATES)[3], 1.2)
        with self.assertRaises(ValueError):
            cash_estimate(2.5)

    def test_scope_and_exact_origin(self):
        params = (22.413612, 114.210276, ["metals"])
        self.assertEqual(len(query_plan(*params)["result"]), 3432)
        self.assertEqual(len(query_plan(*params, scope="只看綠綠賞")["result"]), 606)
        self.assertTrue(query_plan(*params, radius=.5, scope="只看綠綠賞")["result"].empty)
        a, _ = compare_plans(22.340947, 114.179515, ["food waste", "glass bottles"], .5)
        b, _ = compare_plans(22.2819, 114.1582, ["food waste", "glass bottles"], .5)
        self.assertFalse(a.equals(b))

    def test_candidate_choice_and_conversion(self):
        candidates = [{"nameZH":"A", "x":830000, "y":820000}, {"nameZH":"B", "x":840000,"y":830000}]
        with patch("recycling_service.request_json", return_value=candidates):
            self.assertEqual(search_places("大學站"), candidates)
        with patch("recycling_service.request_json", return_value={"wgsLat":22.413612,"wgsLong":114.210276}) as request:
            self.assertEqual(place_coordinates(candidates[1]), (22.413612,114.210276))
            self.assertEqual(request.call_args.args[1]["e"], "840000")

    def make_app(self):
        app = AppTest.from_file(str(APP)).run(timeout=60)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        return app

    def assert_ok(self, app):
        self.assertEqual(len(app.exception), 0, str(app.exception))

    def test_card_returns_to_existing_map(self):
        # Regression: card actions must focus the existing map, request a
        # page scroll, and never open a dialog or enable wheel zoom.
        with patch("streamlit_folium.st_folium", return_value={}) as map_renderer, \
             patch("streamlit_scroll_to_top.scroll_to_here") as scroll:
            app = self.make_app()
            app.checkbox(key="_material_metals").check().run(timeout=60)
            for kind, key in [("公眾回收", "public_map_1"), ("入樽機回贈", "cash_map_1")]:
                app.session_state["_kind"] = kind
                app.session_state["query"] = {**app.session_state["query"], "kind": kind}
                app.run(timeout=60)
                scroll.reset_mock()
                app.button(key=key).click().run(timeout=60)
                self.assert_ok(app)
                focus = app.session_state["map_focus"]
                self.assertEqual(focus["result_rank"], 1)
                self.assertEqual(len(app.get("dialog")), 0)
                scroll.assert_called_once()
                current_map = map_renderer.call_args.args[0]
                self.assertEqual(current_map.location, [float(focus["lat"]), float(focus["lgt"])])
                self.assertIs(current_map.options["scroll_wheel_zoom"], False)
                popups = [child for marker in current_map._children.values()
                          for child in getattr(marker, "_children", {}).values()
                          if child.__class__.__name__ == "Popup"]
                self.assertTrue(any(p.options.get("min_width") == 260 for p in popups))

    def test_native_recommendation_and_clear(self):
        app = self.make_app()
        app.checkbox(key="_material_metals").check().run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.metric[0].value, "3432")
        app.session_state["query"] = {**app.session_state["query"], "lat":22.413612,"lon":114.210276,"scope":"只看綠綠賞"}
        app.session_state["_scope"] = "只看綠綠賞"
        app.session_state["_lat"], app.session_state["_lon"] = 22.413612,114.210276
        app.run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.metric[0].value, "606")
        app.button(key="clear_materials").click().run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.session_state["query"]["materials"], [])
        self.assertEqual(app.session_state["query"]["scope"], "只看綠綠賞")

    def test_native_rewards_and_return_preserves_query(self):
        app = self.make_app()
        app.checkbox(key="_material_paper").check().run(timeout=60)
        query = dict(app.session_state["query"])
        app.session_state["nav"] = "綠綠賞積分與禮品"
        app.run(timeout=60)
        app.selectbox(key="_wallet_material").select(list(RATES)[0]).run(timeout=60)
        app.number_input(key="_wallet_quantity").set_value(10.0)
        app.number_input(key="_wallet_existing").set_value(400.0)
        app.run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.metric[2].value, "1,200.00 分")
        self.assertEqual(app.subheader[2].value, "頂級香米 · 1 公斤")
        app.radio(key="reward_section").set_value("下次想換").run(timeout=60)
        self.assert_ok(app)
        self.assertTrue(any("800.00" in c.value for c in app.caption))
        app.button(key="return_search").click().run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.session_state["query"], query)
        self.assertTrue(app.checkbox(key="_material_paper").value)

    def test_native_cash_and_analysis(self):
        app = self.make_app()
        app.session_state["_kind"] = "入樽機回贈"
        app.session_state["query"] = {**app.session_state["query"], "kind":"入樽機回贈"}
        app.run(timeout=60)
        app.number_input(key="bottles").set_value(31).run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(app.metric[0].value, "HK$3.00")
        self.assertFalse(any(widget.key == "_wallet_material" for widget in app.selectbox))
        app.session_state["nav"] = "推薦依據與分析"
        app.run(timeout=60)
        self.assert_ok(app)
        self.assertGreaterEqual(len(app.dataframe), 3)
        app.radio(key="analysis_section").set_value("推薦方法對照").run(timeout=60)
        self.assert_ok(app)
        app.radio(key="comparison_source").set_value("60 個固定案例").run(timeout=60)
        self.assert_ok(app)
        self.assertEqual(len(app.dataframe[0].value), 3)
        before = app.info[0].value
        app.selectbox(key="fixed_case").set_value(12).run(timeout=60)
        self.assert_ok(app)
        self.assertNotEqual(app.info[0].value, before)
        self.assertIn("中環", app.info[0].value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
