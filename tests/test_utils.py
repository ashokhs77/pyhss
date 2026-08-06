import pytest

from utils import InvalidIMSI, validate_imsi


@pytest.mark.parametrize("imsi", ["1", "12345", "1234567890123456"])
def test_validate_imsi_accepts_variable_lengths(imsi):
    validate_imsi(imsi)


@pytest.mark.parametrize("imsi", ["", "12a34", "+123"])
def test_validate_imsi_rejects_non_numeric_values(imsi):
    with pytest.raises(InvalidIMSI):
        validate_imsi(imsi)
