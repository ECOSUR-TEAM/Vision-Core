SUPPORTED_PRECISIONS = frozenset({"fp32", "fp16", "int8"})
CPU_PRECISIONS = frozenset({"fp32", "int8"})


def is_supported_precision(value: str) -> bool:
    return value in SUPPORTED_PRECISIONS


def is_cpu_precision(value: str) -> bool:
    return value in CPU_PRECISIONS
