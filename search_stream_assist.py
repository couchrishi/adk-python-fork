
import sys
from google.cloud import discoveryengine_v1beta as discoveryengine

print("Searching for StreamAssist...")

# Recursively search for "Stream" or "Assist" in the module structure
def search_module(module, path, depth=0):
    if depth > 3: return
    for name in dir(module):
        if name.startswith('_'): continue
        if "Stream" in name or "Assist" in name:
            print(f"Found match: {path}.{name}")
        
        # simple recursion for submodules
        val = getattr(module, name)
        if hasattr(val, '__package__') and val.__package__ and val.__package__.startswith('google.cloud.discoveryengine'):
             # avoid infinite loops lightly
             pass

search_module(discoveryengine, "discoveryengine")
print("Done.")
