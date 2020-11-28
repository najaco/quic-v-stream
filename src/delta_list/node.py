from typing import Generic, Any, Callable, TypeVar, Dict

E = TypeVar("E")


class Node(Generic[E]):
    def __init__(self, key: int, data: E) -> None:
        self.data: int = data
        self.key: int = key
        self.next: Node[E] = None
        self.prev: Node[E] = None

    def to_dict(self) -> Dict:
        return {
            "data": self.data,
            "key": self.key,
            "next": self.next,
            "prev": self.prev,
        }
