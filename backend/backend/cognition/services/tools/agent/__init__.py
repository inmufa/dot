from backend.cognition.services.tools.agent.agent_tool import AGENT_TOOL
from backend.cognition.services.tools.agent.plan_tools import ENTER_PLAN, EXIT_PLAN
from backend.cognition.services.tools.agent.task_tools import TASK_TOOLS
from backend.cognition.services.widgets.ask_tool import ASK_TOOL
from backend.cognition.services.widgets.present_tool import PRESENT_TOOL

AGENT_TOOLS = [*TASK_TOOLS, ASK_TOOL, PRESENT_TOOL, ENTER_PLAN, EXIT_PLAN, AGENT_TOOL]
