from app.agents.graph import build_skeleton_graph


def test_skeleton_graph_compiles_and_runs():
    graph = build_skeleton_graph()
    result = graph.invoke({"input": "안녕", "output": ""})
    assert result["output"] == "안녕"


async def test_skeleton_graph_ainvoke():
    graph = build_skeleton_graph()
    result = await graph.ainvoke({"input": "내일 2시 예약", "output": ""})
    assert result["output"] == "내일 2시 예약"
