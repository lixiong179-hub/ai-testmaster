"""`_signal_gatherer_collect` 分派/累积护栏（G-8 B5f）。

拆分前 `SignalGatherer.execute` 内是一段 5 分支 if/elif 链，只能靠端到端场景间接覆盖；
拆分后对这些分支单独加锁：
1. kind 查表分派（未知 kind 忽略）
2. 单条输入失败只记日志，不影响后续输入
3. 各 handler 的累积口径（PRD 拼接、xmind payload 合并、变更说明拼接）
4. `_SignalBundle` 的空判定与产物组装口径
"""

from typing import Any

from app.pipelines.steps import _signal_gatherer_collect as collect


class _FakeCtx:
    iteration_id = 7


class _FakeInput:
    def __init__(self, kind: str, file_id: int | None = None, payload: Any = None):
        self.kind = kind
        self.file_id = file_id
        self.payload = payload


def _collect(inputs, project_id: int = 1):
    return collect._collect_input_signals(_FakeCtx(), inputs, project_id)


class TestCollectDispatch:
    def test_unknown_kind_ignored(self):
        bundle = _collect([_FakeInput("unknown_kind")])
        assert bundle.is_empty()

    def test_missing_kind_ignored(self):
        inp = _FakeInput("prd")
        del inp.kind
        assert _collect([inp]).is_empty()

    def test_handler_failure_does_not_stop_remaining_inputs(self, monkeypatch):
        def _boom(bundle, ctx, inp, project_id):
            raise RuntimeError("boom")

        monkeypatch.setitem(collect._INPUT_HANDLERS, "prd", _boom)
        bundle = _collect([_FakeInput("prd"), _FakeInput("change_notes", payload={"notes": "变更A"})])
        assert bundle.change_notes == "变更A"

    def test_every_known_kind_has_handler(self):
        assert set(collect._INPUT_HANDLERS) == {"prd", "prototype", "testpoint", "change_notes", "xmind"}


class TestInputHandlers:
    def test_prd_parts_joined_with_separator(self, monkeypatch):
        monkeypatch.setattr(collect, "_load_file_content", lambda ctx, fid, pid: f"内容{fid}")
        bundle = _collect([_FakeInput("prd", file_id=1), _FakeInput("prd", file_id=2)])
        assert bundle.prd_content == "\n\n内容1\n\n内容2"
        assert bundle.file_ids_used == [1, 2]

    def test_prd_without_file_id_records_no_file(self, monkeypatch):
        monkeypatch.setattr(collect, "_load_file_content", lambda ctx, fid, pid: "")
        bundle = _collect([_FakeInput("prd", file_id=None)])
        assert bundle.is_empty()
        assert bundle.file_ids_used == []

    def test_prototype_extends_all_three_lists(self, monkeypatch):
        monkeypatch.setattr(
            collect,
            "_load_ui_from_input",
            lambda ctx, inp, pid: ([{"screen_id": 1}], [{"screen_id": 1}], [9]),
        )
        bundle = _collect([_FakeInput("prototype")])
        assert bundle.ui_descriptions == [{"screen_id": 1}]
        assert bundle.ui_specs == [{"screen_id": 1}]
        assert bundle.file_ids_used == [9]

    def test_testpoint_extends_points(self, monkeypatch):
        monkeypatch.setattr(collect, "_load_test_points_from_input", lambda ctx, inp, pid: [{"id": 3}])
        assert _collect([_FakeInput("testpoint")]).test_points == [{"id": 3}]

    def test_change_notes_empty_not_appended(self, monkeypatch):
        # `_load_change_notes_from_input` 对空值已返回 ""，handler 不应把空串塞进列表
        monkeypatch.setattr(collect, "_load_change_notes_from_input", lambda inp: "")
        assert _collect([_FakeInput("change_notes")]).change_notes_parts == []

    def test_xmind_merges_payload_and_content(self, monkeypatch):
        monkeypatch.setattr(collect, "_load_file_content", lambda ctx, fid, pid: '{"module": "m", "point": "p"}')
        inp = _FakeInput("xmind", file_id=5, payload={"origin": "manual"})
        bundle = _collect([inp])
        assert bundle.test_points[0]["module"] == "m"
        assert inp.payload == {"origin": "manual"}, "原 payload 不应被就地修改"

    def test_xmind_without_content_yields_nothing(self, monkeypatch):
        monkeypatch.setattr(collect, "_load_file_content", lambda ctx, fid, pid: "")
        assert _collect([_FakeInput("xmind", file_id=5)]).test_points == []


class TestSignalBundle:
    def test_empty_when_only_blank_parts(self):
        bundle = collect._SignalBundle(prd_parts=["   "], change_notes_parts=["", " "])
        assert bundle.is_empty() is True

    def test_not_empty_when_any_signal_present(self):
        assert collect._SignalBundle(ui_descriptions=[{"screen_id": 1}]).is_empty() is False
        assert collect._SignalBundle(test_points=[{"id": 1}]).is_empty() is False
        assert collect._SignalBundle(prd_parts=["\n\n内容"]).is_empty() is False

    def test_to_payload_flags_and_ids(self):
        bundle = collect._SignalBundle(
            prd_parts=["\n\n需求A"],
            ui_specs=[{"screen_id": 1}],
            ui_descriptions=[{"screen_id": 1}],
            test_points=[{"id": 1}],
            change_notes_parts=["变更说明"],
            file_ids_used=[4],
        )
        payload = bundle.to_payload(_FakeCtx(), 5, True)
        assert payload["iteration_id"] == 7
        assert payload["project_id"] == 5
        assert payload["prd_content"] == "需求A"
        assert payload["has_prd"] is True
        assert payload["has_ui"] is True
        assert payload["has_testpoints"] is True
        assert payload["has_change_notes"] is True
        assert payload["is_old_project"] is True
        assert payload["file_ids_used"] == [4]

    def test_to_payload_empty_flags(self):
        payload = collect._SignalBundle().to_payload(_FakeCtx(), 5, False)
        assert payload["prd_content"] == ""
        assert payload["has_prd"] is False
        assert payload["has_ui"] is False
        assert payload["has_testpoints"] is False
        assert payload["has_change_notes"] is False
