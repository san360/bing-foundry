#!/usr/bin/env python3
"""
Diagnostic script to test if UI components can be imported and rendered.
Run this to check if there are any import or runtime errors.
"""
import sys
from pathlib import Path

# Add src to path (same as app.py does)
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("=" * 60)
print("UI Components Import Test")
print("=" * 60)

# Test 1: Check if streamlit is available
try:
    import streamlit as st
    print("✅ streamlit imported successfully")
except ImportError as e:
    print(f"❌ streamlit import failed: {e}")
    print("   Run: pip install streamlit")
    sys.exit(1)

# Test 2: Check infrastructure imports
try:
    from infrastructure import AzureConfig, MARKET_OPTIONS
    print("✅ infrastructure module imported successfully")
    print(f"   Found {len(MARKET_OPTIONS)} market options")
except Exception as e:
    print(f"❌ infrastructure import failed: {e}")
    sys.exit(1)

# Test 3: Check services imports
try:
    from services import RiskAnalyzer
    print("✅ services module imported successfully")
except Exception as e:
    print(f"❌ services import failed: {e}")
    sys.exit(1)

# Test 4: Check scenarios imports
try:
    from scenarios import DirectAgentScenario, MCPAgentScenario, MCPRestAPIScenario
    print("✅ scenarios module imported successfully")
except Exception as e:
    print(f"❌ scenarios import failed: {e}")
    sys.exit(1)

# Test 5: Check UI component imports
try:
    from ui.components.sidebar import render_sidebar
    print("✅ ui.components.sidebar imported successfully")
except Exception as e:
    print(f"❌ ui.components.sidebar import failed: {e}")
    sys.exit(1)

# Test 6: Check UI pages imports
try:
    from ui.pages.scenario1 import render_scenario1
    print("✅ ui.pages.scenario1 imported successfully")
except Exception as e:
    print(f"❌ ui.pages.scenario1 import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from ui.pages.scenario2 import render_scenario2
    print("✅ ui.pages.scenario2 imported successfully")
except Exception as e:
    print(f"❌ ui.pages.scenario2 import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from ui.pages.scenario3 import render_scenario3
    print("✅ ui.pages.scenario3 imported successfully")
except Exception as e:
    print(f"❌ ui.pages.scenario3 import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from ui.pages.documentation import render_documentation
    print("✅ ui.pages.documentation imported successfully")
except Exception as e:
    print(f"❌ ui.pages.documentation import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL IMPORTS SUCCESSFUL!")
print("=" * 60)
print("\nIf imports work but UI doesn't load:")
print("1. Check browser console for JavaScript errors")
print("2. Try clearing Streamlit cache: streamlit cache clear")
print("3. Check if tabs are clickable in the browser")
print("4. Look for any error messages in the Streamlit terminal")
print("\nTo run the app:")
print("  streamlit run src/ui/app.py")
print("=" * 60)
