import os
from api.services.validator import validate_execution_output
from api.models.job import ValidationStrategy
from dotenv import load_dotenv

load_dotenv()

def test_ai_validation():
    print("Testing AI Validation...")
    output = "The first number is 2. The second number is 2."
    requirements = {
        "task": "Extract the numbers from the text and calculate their sum",
        "expected_sum": 4
    }
    
    result = validate_execution_output(output, requirements)
    print(f"Strategy: {result.strategy}")
    print(f"Verified: {result.verified}")
    print(f"Reason: {result.reason}")

if __name__ == "__main__":
    test_ai_validation()
