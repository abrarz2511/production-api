
from typing import Optional

from typing_extensions import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable

from config import get_settings
class AgentState(TypedDict):
    "The AgentState for production agent"
    messages: Annotated[List[BaseMessage], add_messages]    #add_messages here is a reducer function, with this langgraph appends messages instead of replacing in the agent state
    error: Optional[str]
    retry_count: int
    model_used: str

class ProductionAgent:
    """Production Agent that manages conversation state, interacts with LLM, and handles retries and fallbacks"""

    def __init__(self):
        settings = get_settings()

        self.primary_llm = ChatOpenAI(model=settings.primary_model, temperature=0, timeout=30, max_retries=0, openai_api_key=settings.OPENAI_API_KEY)
        self.fallback_llm = ChatOpenAI(model=settings.fallback_model, temperature=0, timeout = 30, max_retries=0, openai_api_key=settings.OPENAI_API_KEY)
        self.max_retries = settings.MAX_RETRIES
        self.graph = self._build_graph()

    def _build_graph(self):

        def process_messages(state: AgentState) -> AgentState:
            try:
                response = self.primary_llm.invoke(state["messages"])

                return {
                    "messages": [response],
                    "error": None,
                    "model_used": "primary"
                }

            except Exception as e:
                return {
                    "messages": state["messages"],
                    "error": str(e),
                    "model_used": "primary"
                }
            
        def fallback(state: AgentState) -> AgentState:
            try:
                response = self.fallback_llm.invoke(state["messages"])

                return {
                    "messages": [response],
                    "error": None,
                    "model_used": "fallback"
                }

            except Exception as e:
                return {
                    "messages": state["messages"],
                    "error": str(e),
                    "model_used": "fallback"
                }

        def handle_error(state: AgentState) -> AgentState:
            return {
                "messages": [
                    AIMessage(content=(f"I'm sorry, but I'm having trouble processing your request right now. Please try again later."))
                ],
                "model_used": "error_handler",
            }

        def route_after_process(state: AgentState) -> str:
            if state.get("error") is None:
                return "done"
            elif state["error"]:
                return "fallback"
            else:
                return "error"
            
        def route_after_fallback(state: AgentState) -> str:
            if state.get("error") is None:
                return "done"
            else:
                return "error"

        graph = StateGraph(AgentState)
        graph.add_node("process", process_messages)
        graph.add_node("fallback", fallback)
        graph.add_node("error", handle_error)
        graph.add_edge(START, "process")
        graph.add_conditional_edges("process", route_after_process, {"done": END, "fallback": "fallback", "error": "error"})
        graph.add_conditional_edges("fallback", route_after_fallback, {"done": END, "error": "error"})

        graph.add_edge("error", END)

        return graph.compile()

    @traceable(name="production_agent_invoke")
    def invoke(self, message: str) -> dict:
        result = self.graph.invoke({
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": "",
        })
        return {
            "response": result["messages"][-1].content,
            "model_used": result.get("model_used", "unknown"),
            "error": result.get("error"),
        }
