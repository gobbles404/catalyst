"""Every test session registers the probes, the one way anything registers them: by importing
their package, as a host does when its config names it under `probes`. An end user's build
never imports it, and `test_end_user_build.py` holds that in a Python of its own.
"""

import catalyst_probes

__all__ = ["catalyst_probes"]
