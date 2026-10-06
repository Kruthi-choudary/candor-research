class PipelineError(Exception):
    """Expected, user-facing pipeline failure (bad input, missing data, upstream API failure).

    Caught at the CLI boundary and shown as a clean [ERROR] message instead of a traceback.
    An exception that is NOT a PipelineError is treated as a real bug and allowed to propagate.
    """
