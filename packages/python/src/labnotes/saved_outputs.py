from labnotes.notebook_kernel import NotebookKernel, block_key
from labnotes.python_blocks import python_blocks


def saved_outputs(kernel: NotebookKernel | None, content: str) -> list[str]:
    if kernel is None:
        return []
    return [kernel.outputs.get(block_key(code), "") for code in python_blocks(content)]
