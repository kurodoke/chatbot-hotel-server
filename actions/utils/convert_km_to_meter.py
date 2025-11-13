from typing import Union

def convert_to_meters(s: Union[str, float]) -> float:
    """
    Convert a string representing a distance with units to meters.

    Args:
        s (Union[str, float]): The string or float representing the distance.

    Returns:
        float: The distance in meters.

    Raises:
        ValueError: If the unit in the string is not 'km' or 'm'.
    """
    if isinstance(s, str):
        if s.endswith('km'):
            return float(s[:-2]) * 1000
        elif s.endswith('m'):
            return float(s[:-1])
        else:
            raise ValueError('Invalid unit')
    elif isinstance(s, float):
        return s
    else:
        raise TypeError('Invalid input type')
