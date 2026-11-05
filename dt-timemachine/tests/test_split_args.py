"""Run: python tests/test_split_args.py  -- checks Windows-path handling without needing Windows."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proxy import split_args

win = r'C:\Users\abdul\Downloads\Timemachine_1301\dt-timemachine\tests\fake_upstream.py'
assert split_args(win, windows=True) == [win]
assert split_args('"' + win.replace("tests", "my tests") + '"', windows=True) == [win.replace("tests", "my tests")]
assert split_args("-y @dynatrace-oss/dynatrace-mcp-server", windows=True) == ["-y", "@dynatrace-oss/dynatrace-mcp-server"]
assert split_args("/c npx -y pkg", windows=True) == ["/c", "npx", "-y", "pkg"]
assert split_args("-y pkg", windows=False) == ["-y", "pkg"]
print("PASS: argument splitting keeps Windows paths intact")