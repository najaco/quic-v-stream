from typing import Generic, Dict, TypeVar, List, Tuple

from .node import Node

E = TypeVar("E")


class DeltaList(Generic[E]):
    def __init__(self):
        self.__head: Node[E] = None
        self.__tail: Node[E] = None
        self.__size: int = 0
        self.__nodes: Dict[E, Node[E]] = {}
        self.__cumulative_key: int = 0

    def insert(self, k: int, e: E) -> None:
        if e in self.__nodes:
            raise Exception(str(e), " already exists.")
        if self.__size == 0:
            self.__nodes[e] = Node[E](key=k, data=e)
            self.__size += 1
            self.__head = self.__nodes[e]
            self.__tail = self.__head
            self.__cumulative_key = k
            return
        elif k < self.__head.key:
            self.__insert_first(k, e)
        elif k >= self.__cumulative_key:
            self.__nodes[e] = Node[E](key=k - self.__cumulative_key, data=e)
            self.__size += 1
            old_tail: Node[E] = self.__tail
            self.__tail = self.__nodes[e]
            old_tail.next = self.__nodes[e]
            self.__tail.prev = old_tail
            self.__cumulative_key = k
        else:
            p: Node[E] = self.__head
            while k - p.key >= 0:
                k -= p.key
                p = p.next
            self.__nodes[e] = Node[E](key=k, data=e)
            self.__size += 1
            p.prev.next = self.__nodes[e]
            self.__nodes[e].prev = p.prev
            p.prev = self.__nodes[e]
            self.__nodes[e].next = p

    def decrement_key(self, delta: int = 1) -> None:
        if self.__size > 0:
            self.__head.key -= delta
            self.__cumulative_key -= delta

    def remove(self, e: E) -> bool:
        if e not in self.__nodes:
            raise Exception(str(e), " does not exist.")
        if self.__nodes[e] == self.__head:
            if self.__head.next is not None:
                self.__nodes[e].next.key += self.__head.key  # update key of next node
            self.__head = self.__nodes[e].next
            self.__size -= 1
            del self.__nodes[e]
        elif self.__nodes[e] == self.__tail:
            self.remove_last()
        else:
            self.__nodes[e].prev.next = self.__nodes[e].next
            self.__nodes[e].next.prev = self.__nodes[e].prev
            self.__nodes[e].next.key += self.__nodes[e].key  # update key of next node
            self.__size -= 1
            del self.__nodes[e]
        return True

    def remove_all_ready(self) -> List[E]:
        ready_list: List[E] = []
        while self.__size > 0 and self.__head.key <= 0:
            ready_list.append(self.remove_first())
        return ready_list

    def remove_first(self) -> E:
        if self.__size == 0:
            return None

        data = self.__head.data
        self.__head = self.__head.next
        if self.__head is not None:
            self.__head.key += self.__nodes[data].key
            self.__head.prev = None
        else:
            self.__cumulative_key = 0
        self.__size -= 1
        del self.__nodes[data]
        return data

    def remove_last(self) -> E:
        if self.__size == 0:
            return None
        n: Node[E] = self.__tail
        if self.__size == 1:
            self.__head = None
            self.__tail = None
        else:
            self.__tail.prev.next = self.__tail.next
            self.__tail = self.__tail.prev
        self.__cumulative_key -= n.key
        self.__size -= 1
        del self.__nodes[n.data]
        return n.data

    def contains(self, e: E) -> bool:
        return e in self.__nodes

    def __insert_first(self, k: int, e: E) -> None:
        self.__nodes[e] = Node[E](key=k, data=e)
        self.__size += 1
        self.__head.key -= k
        self.__head.prev = self.__nodes[e]
        self.__nodes[e].next = self.__head
        self.__head = self.__nodes[e]

    def to_list(self) -> List[Tuple[int, E]]:
        l: List[Tuple[int, E]] = []
        node: Node[E] = self.__head
        while node is not None:
            l.append((node.key, node.data))
            node = node.next
        return l

    @property
    def size(self) -> int:
        return self.__size

    @property
    def head(self) -> Node[E]:
        return self.__head

    @property
    def tail(self) -> Node[E]:
        return self.__tail

    def print_list(self) -> None:
        p = self.__head
        while p is not None:
            print("{} : {}".format(p.key, p.data))
            p = p.next
