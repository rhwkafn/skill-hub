"""Binary search implementation in Python."""


def binary_search(arr: list, target: int) -> int:
    """Search for target in a sorted array using binary search.

    Args:
        arr: A sorted list of integers.
        target: The value to search for.

    Returns:
        The index of target if found, otherwise -1.

    Examples:
        >>> binary_search([1, 3, 5, 7, 9], 5)
        2
        >>> binary_search([1, 3, 5, 7, 9], 4)
        -1
        >>> binary_search([], 1)
        -1
    """
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


def binary_search_recursive(arr: list, target: int, left: int = 0, right: int | None = None) -> int:
    """Recursive binary search implementation.

    Args:
        arr: A sorted list of integers.
        target: The value to search for.
        left: Left boundary index.
        right: Right boundary index.

    Returns:
        The index of target if found, otherwise -1.
    """
    if right is None:
        right = len(arr) - 1

    if left > right:
        return -1

    mid = left + (right - left) // 2

    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search_recursive(arr, target, mid + 1, right)
    else:
        return binary_search_recursive(arr, target, left, mid - 1)


if __name__ == "__main__":
    # Quick smoke tests
    test_arr = [1, 3, 5, 7, 9, 11, 13, 15]

    assert binary_search(test_arr, 7) == 3
    assert binary_search(test_arr, 1) == 0
    assert binary_search(test_arr, 15) == 7
    assert binary_search(test_arr, 4) == -1
    assert binary_search([], 1) == -1

    assert binary_search_recursive(test_arr, 7) == 3
    assert binary_search_recursive(test_arr, 1) == 0
    assert binary_search_recursive(test_arr, 15) == 7
    assert binary_search_recursive(test_arr, 4) == -1
    assert binary_search_recursive([], 1) == -1

    print("All tests passed.")
