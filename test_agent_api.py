#!/usr/bin/env python3
"""Quick test to verify agent API calls are correct."""

# Check the source code directly
with open('src/services/agent_service.py', 'r') as f:
    content = f.read()

if 'project_client.agents.create_version' in content:
    print("✅ agent_service.py uses create_version (correct)")
else:
    print("❌ agent_service.py does NOT use create_version")

if 'project_client.agents.create_agent' in content:
    print("❌ agent_service.py uses create_agent (wrong)")
else:
    print("✅ agent_service.py does NOT use create_agent (correct)")

# Show the relevant lines
print("\n=== Relevant lines in agent_service.py ===")
for i, line in enumerate(content.split('\n'), 1):
    if 'agents.' in line and 'create' in line:
        print(f"Line {i}: {line.strip()}")
