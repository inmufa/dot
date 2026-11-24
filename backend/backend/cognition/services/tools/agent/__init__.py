from backend.cognition.services.tools.agent.agent_tool import AGENT_TOOL
from backend.cognition.services.tools.agent.plan_tools import ENTER_PLAN, EXIT_PLAN
from backend.cognition.services.tools.agent.question_tool import QUESTION_TOOL
from backend.cognition.services.tools.agent.task_tools import TASK_TOOLS

AGENT_TOOLS = [*TASK_TOOLS, QUESTION_TOOL, ENTER_PLAN, EXIT_PLAN, AGENT_TOOL]
