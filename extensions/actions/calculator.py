defination = '''
function calculator(expression: str) -> str:

arguments:
- expression: Math expression to calculate

Example usage:
calculator("12 * 6")
calculator("calculate 20 + 30")
calculator("what is 100 / 4")
calculator("2 ** 10")
calculator("sqrt(144)")
'''

import os
import re
import math
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

# Safe math functions allowed in expressions
SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "pow":  math.pow,
    "abs":  abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "log":  math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin":  math.sin,
    "cos":  math.cos,
    "tan":  math.tan,
    "pi":   math.pi,
    "e":    math.e,
    "round": round,
}

def _clean_expression(expression: str) -> str:
    """Strip natural language prefixes."""
    prefixes = [
        "calculate", "what is", "what's", "compute",
        "solve", "evaluate", "find", "tell me"
    ]
    expr = expression.lower().strip()
    for prefix in prefixes:
        if expr.startswith(prefix):
            expr = expr[len(prefix):].strip()
    # Replace 'x' used as multiply if surrounded by numbers
    expr = re.sub(r'(\d)\s*x\s*(\d)', r'\1*\2', expr)
    return expr

def calculator(expression: str) -> str:
    if not expression.strip():
        return "Please provide a math expression."

    expr = _clean_expression(expression)

    if DEBUG:
        print(f"Evaluating: {expr}")

    try:
        # Safe eval — only allow math functions, no builtins
        result = eval(expr, {"__builtins__": {}}, SAFE_FUNCTIONS)

        # Clean up result display
        if isinstance(result, float) and result.is_integer():
            result = int(result)

        return f"{expression.strip()} = {result}"

    except ZeroDivisionError:
        return "Error: Division by zero."
    except Exception as e:
        return f"Could not calculate '{expression}'. Make sure it's a valid math expression."


if __name__ == "__main__":
    print(calculator("12 * 6"))
    print(calculator("calculate 20 + 30"))
    print(calculator("what is 100 / 4"))
    print(calculator("sqrt(144)"))
    print(calculator("2 ** 10"))
    print(calculator("pi * 5 ** 2"))
    print(calculator("log10(1000)"))