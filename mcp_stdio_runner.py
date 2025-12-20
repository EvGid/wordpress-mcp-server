import asyncio
import os
import sys
import logging

# REDIRECT EVERYTHING UNEXPECTED TO STDERR IMMEDIATELY
# This prevents any library or import noise from corrupting the MCP stream
_original_stdout = sys.stdout
sys.stdout = sys.stderr

# Ensure logging goes to stderr as well
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)

# Standard boilerplate for paths
script_dir = os.path.dirname(os.path.abspath(__file__))
my_mcp_dir = os.path.join(script_dir, "My_MCP")
sys.path.insert(0, my_mcp_dir)

# Import happens with sys.stdout redirected
try:
    import mcp_server
except ImportError as e:
    logging.error(f"Failed to import mcp_server: {e}")
    sys.exit(1)

if __name__ == "__main__":
    # RESTORE original stdout ONLY when calling run
    # sys.__stdout__ is the true underlying stdout
    sys.stdout = sys.__stdout__
    
    try:
        # FastMCP.run(transport="stdio") will take over stdin/stdout
        mcp_server.mcp.run(transport="stdio")
    except Exception as e:
        logging.critical(f"Server error: {e}")
        # Make sure we don't print to the now-restored stdout on failure
        sys.stdout = sys.stderr
        sys.exit(1)
