import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_i256_to_float(data: bytes, start_pos: int, decimal_precision: int = 12) -> Optional[float]:
    """
    Parses an I256 value from binary data starting at a given position and converts it to a float.

    Args:
        data (bytes): The binary data to parse.
        start_pos (int): The starting position of the I256 value in the data.
        decimal_precision (int): The decimal precision for conversion.

    Returns:
        Optional[float]: The parsed float value or None if an error occurs.
    """
    try:
        if len(data) < start_pos + 32:
            raise ValueError("Insufficient data for I256 value.")
        int_value = int.from_bytes(data[start_pos:start_pos + 32], byteorder='little', signed=True)
        return int_value / (10 ** decimal_precision)
    except Exception as e:
        logger.error(f"Error parsing data at position {start_pos}: {e}")
        return None


def extract_commission_values(binary_data: bytes) -> Tuple[Optional[float], Optional[float]]:
    """
    Extracts commission rate and max commission change per epoch as floats from binary data.

    Args:
        binary_data (bytes): The binary data from which to extract the commission values.

    Returns:
        Tuple[Optional[float], Optional[float]]: A tuple containing the commission rate and max commission change,
                                                  or None for each if an error occurs.
    """
    commission_rate = parse_i256_to_float(binary_data, 1)  # Assumes the first byte is not part of the I256 value.
    max_commission_change = parse_i256_to_float(binary_data, 33)
    return commission_rate, max_commission_change
