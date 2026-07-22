"""
Athena MCP Server

Exposes Athena tools and dynamic skills via the MCP protocol.
"""
import sys
import os
import logging

logger = logging.getLogger(__name__)

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from mcp.server.fastmcp import FastMCP
    FAST_MCP_AVAILABLE = True
except ImportError:
    FAST_MCP_AVAILABLE = False

if FAST_MCP_AVAILABLE:
    mcp = FastMCP("Athena Tools")

    # Dynamic skill loading from skills directory
    def _load_skills():
        try:
            from athena.skills import SkillEngine
            from athena.memory import MemoryEngine
            memory = MemoryEngine()
            engine = SkillEngine(llm_generate_fn=lambda x: "", memory=memory)
            for skill_info in engine.list_all():
                func = engine.get(skill_info.function_name)
                if func is not None:
                    mcp.tool()(func)
                    logger.info(f"[MCP] Registered skill: {skill_info.function_name}")
        except Exception as e:
            logger.warning(f"[MCP] Skill loading warning: {e}")

    _load_skills()

if __name__ == "__main__":
    if FAST_MCP_AVAILABLE:
        mcp.run()
    else:
        print("[MCP] FastMCP is not installed.")
