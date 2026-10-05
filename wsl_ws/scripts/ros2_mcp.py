#!/usr/bin/env python3
"""ROS 2 & Isaac Sim Model Context Protocol (MCP) Server.

Exposes live ROS 2 Jazzy graph, active topics, joint states, and simulation status
to OpenCode agents running on the host system.
Communicates via standard JSON-RPC 2.0 over stdio (MCP standard).
"""

import sys
import json
import subprocess
import shutil

TOOLS = [
    {
        "name": "get_node_graph",
        "description": "Lists all active ROS 2 nodes and topics in the running workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "check_isaac_sim_status",
        "description": "Checks whether Isaac Sim is actively publishing simulation clock (/clock), transforms (/tf), and camera streams.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "echo_topic",
        "description": "Echoes the latest message from a given ROS 2 topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic_name": {
                    "type": "string",
                    "description": "Topic name (e.g. '/fr3_1/joint_states', '/gemini/feedback')"
                },
                "max_count": {
                    "type": "integer",
                    "default": 1,
                    "description": "Number of messages to capture"
                }
            },
            "required": ["topic_name"]
        }
    }
]


def run_command(cmd_list, timeout=5):
    """Run shell command in WSL2 environment and return stdout."""
    try:
        res = subprocess.run(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return res.stdout.strip() if res.returncode == 0 else f"Error: {res.stderr.strip()}"
    except Exception as e:
        return f"Execution failed: {str(e)}"


def handle_call_tool(name, arguments):
    if name == "get_node_graph":
        nodes = run_command(["ros2", "node", "list"])
        topics = run_command(["ros2", "topic", "list"])
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"=== Active ROS 2 Nodes ===\n{nodes}\n\n=== Active Topics ===\n{topics}"
                }
            ]
        }
    elif name == "check_isaac_sim_status":
        topics = run_command(["ros2", "topic", "list"])
        clock_active = "/clock" in topics
        tf_active = "/tf" in topics
        cam_active = "/overhead_camera/rgb" in topics
        status_text = (
            f"Simulation Status:\n"
            f"- PhysX Clock (/clock): {'ONLINE' if clock_active else 'OFFLINE'}\n"
            f"- Transform Tree (/tf): {'ONLINE' if tf_active else 'OFFLINE'}\n"
            f"- Overhead Camera (/overhead_camera/rgb): {'ONLINE' if cam_active else 'OFFLINE'}\n"
        )
        return {"content": [{"type": "text", "text": status_text}]}
    elif name == "echo_topic":
        topic = arguments.get("topic_name", "")
        count = str(arguments.get("max_count", 1))
        out = run_command(["ros2", "topic", "echo", "--once", topic], timeout=6)
        return {"content": [{"type": "text", "text": out}]}
    else:
        return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ros2-isaac-bridge", "version": "1.0.0"}
                }
            }
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = handle_call_tool(tool_name, arguments)
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }
        elif method == "notifications/initialized":
            continue
        else:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"}
            }

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
