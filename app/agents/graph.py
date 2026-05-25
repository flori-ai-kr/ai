"""LangGraph 스켈레톤.

기반 SPEC(AI-001)에서는 그래프가 "컴파일·호출 가능"함만 보장한다. 실제 에이전트
토폴로지(의도 파악 → 도구 호출 → 응답)와 ReAct 루프는 SPEC-AI-002에서 구현한다.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class SkeletonState(TypedDict):
    input: str
    output: str


def _echo_node(state: SkeletonState) -> dict:
    return {"output": state["input"]}


def build_skeleton_graph() -> CompiledStateGraph:
    """최소 StateGraph: 입력을 그대로 출력으로 흘려보낸다(골격 검증용)."""
    graph = StateGraph(SkeletonState)
    graph.add_node("echo", _echo_node)
    graph.add_edge(START, "echo")
    graph.add_edge("echo", END)
    return graph.compile()
