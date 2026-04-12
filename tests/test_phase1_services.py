from api.models.job import ValidationStrategy
from api.services.signer import result_signer
from api.services.validator import validate_execution_output


def test_validate_execution_output_deterministic_match():
    result = validate_execution_output("4\n", {"expected_output": "4"})

    assert result.verified is True
    assert result.strategy == ValidationStrategy.DETERMINISTIC


def test_validate_execution_output_rejects_error_markers():
    result = validate_execution_output("[ERROR] Process exited with code 1.", {})

    assert result.verified is False
    assert result.strategy == ValidationStrategy.RULE_BASED


def test_result_signer_is_deterministic_for_same_payload():
    payload = {
        "job_id": "job-123",
        "output": "hello-world",
        "verified": True,
        "timestamp": "2026-04-03T00:00:00+00:00",
    }

    signature_a = result_signer.sign_payload(payload)
    signature_b = result_signer.sign_payload(payload)

    assert signature_a == signature_b
    assert result_signer.public_key
